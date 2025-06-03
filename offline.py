import requests
import os
import web
import youtube
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import time
import logging
import json
import atexit
import signal
import sys
from typing import Optional, Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Track downloaded items by URL
downloaded_urls = set()
online_urls = set()

# Global executor tracking
_active_executors = []
_executor_lock = threading.Lock()
_shutdown_flag = threading.Event()

def _register_executor(executor):
    """Register an executor for proper cleanup"""
    with _executor_lock:
        _active_executors.append(executor)

def _unregister_executor(executor):
    """Unregister an executor"""
    with _executor_lock:
        if executor in _active_executors:
            _active_executors.remove(executor)

def _cleanup_executors():
    """Emergency cleanup of all active executors"""
    logger.info("Emergency cleanup of executors initiated")
    with _executor_lock:
        for executor in _active_executors[:]:  # Copy list to avoid modification during iteration
            try:
                executor.shutdown(wait=False)
                logger.info("Executor shutdown completed")
            except Exception as e:
                logger.error(f"Error during executor cleanup: {e}")
        _active_executors.clear()

# Register cleanup handlers
atexit.register(_cleanup_executors)

def _signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, initiating shutdown")
    _shutdown_flag.set()
    _cleanup_executors()
    sys.exit(0)

# Register signal handlers for graceful shutdown
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, _signal_handler)
if hasattr(signal, 'SIGINT'):
    signal.signal(signal.SIGINT, _signal_handler)

def sync(token: str, path: str, resolution: str, delimiter: str, VIDEO: bool, stop_event: Optional[threading.Event] = None) -> bool:
    """
    Sync Raindrop.io bookmarks to local storage with robust error handling and cancellation support.
    
    Args:
        token: Raindrop.io API token
        path: Local storage path
        resolution: Video resolution for downloads
        delimiter: Delimiter for config file (now unused, kept for compatibility)
        VIDEO: Whether to download videos
        stop_event: Threading event for graceful cancellation
    
    Returns:
        bool: True if sync completed successfully, False otherwise
    """
    start_time = time.time()
    executor = None
    futures = []
    
    try:
        logger.info("Starting sync operation")
        
        # Check for global shutdown flag
        if _shutdown_flag.is_set():
            logger.info("Global shutdown flag detected, aborting sync")
            return False
        
        # Early cancellation check
        if stop_event and stop_event.is_set():
            logger.info("Sync cancelled before starting")
            return False
        
        # Initialize directory structure
        path = verify_directory_structure(path)
        
        # Get bookmarks from API
        headers = Auth(token)
        bookmarks = get_bookmarks(headers)
        
        if not bookmarks:
            logger.warning("No bookmarks retrieved from API")
            return False
            
        logger.info(f"Retrieved {len(bookmarks)} bookmarks from API")
        
        # Check for cancellation after API call
        if stop_event and stop_event.is_set() or _shutdown_flag.is_set():
            logger.info("Sync cancelled after API call")
            return False
        
        # Create required directories
        _create_directories(path, VIDEO)
        
        # Clear online list and prepare for sync
        download_lock = threading.Lock()
        online_urls.clear()
        downloaded_urls.clear()
        
        # Scan existing files to populate downloaded_urls
        _scan_existing_files(path)
        
        # Determine optimal number of workers based on system and bookmark count
        max_workers = min(5, max(2, len(bookmarks) // 20))
        logger.info(f"Using {max_workers} worker threads")
        
        # Create thread pool executor with proper cleanup
        try:
            executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="SyncWorker")
            _register_executor(executor)
        except Exception as e:
            logger.error(f"Failed to create ThreadPoolExecutor: {e}")
            return False
        
        # Create download function with proper error handling
        def download_bookmark_safe(bookmark: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Safe wrapper for bookmark download with comprehensive error handling"""
            if stop_event and stop_event.is_set() or _shutdown_flag.is_set():
                return None
            
            try:
                return _download_single_bookmark(bookmark, path, resolution, VIDEO, download_lock, stop_event)
            except Exception as e:
                logger.error(f"Unexpected error downloading bookmark {bookmark.get('link', 'unknown')}: {e}")
                return None
        
        # Submit all download tasks with shutdown protection
        try:
            for i, bookmark in enumerate(bookmarks):
                # Check for shutdown before submitting each task
                if stop_event and stop_event.is_set() or _shutdown_flag.is_set():
                    logger.info("Sync cancelled during task submission")
                    break
                
                # Extra safety check - ensure executor is still alive
                if executor._shutdown:
                    logger.warning("Executor already shutdown, stopping task submission")
                    break
                    
                try:
                    future = executor.submit(download_bookmark_safe, bookmark)
                    futures.append(future)
                except RuntimeError as e:
                    if "cannot schedule new futures after interpreter shutdown" in str(e):
                        logger.error("Interpreter shutdown detected during task submission")
                        break
                    else:
                        logger.error(f"Runtime error submitting task {i}: {e}")
                        break
                except Exception as e:
                    logger.error(f"Unexpected error submitting task {i}: {e}")
                    break
                
                # Add small delay to prevent overwhelming the system
                time.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Error submitting download tasks: {e}")
            return False
        
        logger.info(f"Successfully submitted {len(futures)} tasks")
        
        # Process completed futures with timeout and cancellation support
        completed_count = 0
        failed_count = 0
        
        if not futures:
            logger.warning("No tasks were submitted")
            return False
        
        try:
            # Use a shorter timeout per batch to allow for more frequent cancellation checks
            batch_timeout = min(300, len(futures) * 10)  # 5 minutes or 10 seconds per task
            
            for future in as_completed(futures, timeout=batch_timeout):
                if stop_event and stop_event.is_set() or _shutdown_flag.is_set():
                    logger.info("Sync cancelled during execution")
                    break
                
                try:
                    result = future.result(timeout=120)  # 2 minute timeout per task
                    if result:
                        completed_count += 1
                        if completed_count % 10 == 0:  # Log progress every 10 downloads
                            logger.info(f"Completed {completed_count}/{len(futures)} downloads")
                    else:
                        failed_count += 1
                        
                except TimeoutError:
                    logger.warning("Download task timed out")
                    failed_count += 1
                    future.cancel()
                    
                except Exception as e:
                    logger.error(f"Error processing download result: {e}")
                    failed_count += 1
                    
        except TimeoutError:
            logger.error("Overall sync operation timed out")
            # Don't return False immediately, let cleanup happen
            
        # Log final statistics
        elapsed_time = time.time() - start_time
        success_rate = (completed_count / len(futures)) * 100 if futures else 0
        
        logger.info(f"Sync completed in {elapsed_time:.2f} seconds")
        logger.info(f"Success rate: {success_rate:.1f}% ({completed_count}/{len(futures)})")

        current_bookmarks = bookmarks
        if success_rate >= 80:  # Only archive if sync was mostly successful
            try:
                _archive_removed_bookmarks_enhanced(path, current_bookmarks)
            except Exception as e:
                logger.error(f"Error during archive process: {e}")
        
        if failed_count > 0:
            logger.warning(f"{failed_count} downloads failed")

        return success_rate >= 80  # Consider sync successful if 80% or more completed
        
    except KeyboardInterrupt:
        logger.info("Sync interrupted by user")
        return False
        
    except Exception as e:
        logger.error(f"Critical error during sync: {e}")
        return False
        
    finally:
        # Cleanup: Cancel remaining futures and shutdown executor
        if executor:
            try:
                logger.info("Shutting down thread pool executor")
                
                # Cancel all remaining futures
                for future in futures:
                    if not future.done():
                        future.cancel()
                
                # Unregister before shutdown
                _unregister_executor(executor)
                
                # Shutdown executor with timeout
                executor.shutdown(wait=False)
                
                # Give a bit of time for threads to finish gracefully
                if not (_shutdown_flag.is_set() or (stop_event and stop_event.is_set())):
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error during executor cleanup: {e}")

def _scan_existing_files(path: str) -> None:
    """Scan existing files to populate downloaded_urls set"""
    try:
        # Scan article files
        article_dir = os.path.join(path, "article")
        if os.path.exists(article_dir):
            for filename in os.listdir(article_dir):
                if filename.endswith('.html'):
                    # Extract URL from filename if possible, or just track the existence
                    downloaded_urls.add(filename[:-5])  # Remove .html extension
                    
        # Scan video files
        video_dir = os.path.join(path, "video")
        if os.path.exists(video_dir):
            for filename in os.listdir(video_dir):
                if filename.endswith('.mp4'):
                    downloaded_urls.add(filename[:-4])  # Remove .mp4 extension
                    
        logger.info(f"Found {len(downloaded_urls)} existing downloads")
    except Exception as e:
        logger.error(f"Error scanning existing files: {e}")

def _download_single_bookmark(bookmark: Dict[str, Any], path: str, resolution: str, VIDEO: bool, 
                             download_lock: threading.Lock, stop_event: Optional[threading.Event]) -> Optional[Dict[str, Any]]:
    """Download a single bookmark with proper error handling and cancellation support"""
    
    if stop_event and stop_event.is_set() or _shutdown_flag.is_set():
        return None
    
    try:
        link = bookmark.get('link')
        title = bookmark.get('title', 'Untitled')
        bookmark_type = bookmark.get('type', 'article')
        
        if not link:
            logger.warning("Bookmark missing link, skipping")
            return None
        
        # Add to online list (thread-safe)
        with download_lock:
            online_urls.add(link)
        
        # Skip if already downloaded (based on title)
        sanitized_title = web.sanitize_filename(title)
        if sanitized_title in downloaded_urls:
            logger.debug(f"Skipping already downloaded: {title}")
            return bookmark
        
        # Check for cancellation before download
        if stop_event and stop_event.is_set() or _shutdown_flag.is_set():
            return None
        
        # Download based on type
        success = False
        
        if bookmark_type == 'article':
            logger.info(f"Downloading article: {title}")
            try:
                web.save_monolith(link, os.path.join(path, 'article'), title)
                success = True
            except Exception as e:
                logger.error(f"Error downloading article {title}: {e}")
                
        elif bookmark_type == 'video' and VIDEO:
            # Check cancellation before video download (can be slow)
            if stop_event and stop_event.is_set() or _shutdown_flag.is_set():
                return None
                
            logger.info(f"Downloading video: {title}")
            try:
                youtube.save(link, os.path.join(path, 'video'), resolution)
                success = True
            except Exception as e:
                logger.error(f"Error downloading video {title}: {e}")
        else:
            # Unknown type or video disabled
            success = True
        
        # Update downloaded set if successful
        if success:
            with download_lock:
                downloaded_urls.add(sanitized_title)
            
            logger.debug(f"Successfully downloaded: {title}")
            return bookmark
        
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error in bookmark download: {e}")
        return None

def _create_directories(path: str, VIDEO: bool) -> None:
    """Create required directory structure"""
    try:
        os.makedirs(path, exist_ok=True)
        os.makedirs(os.path.join(path, "article"), exist_ok=True)
        
        if VIDEO:
            os.makedirs(os.path.join(path, "video"), exist_ok=True)
            
    except Exception as e:
        logger.error(f"Error creating directories: {e}")
        raise

def Auth(token: str) -> Dict[str, str]:
    """Create authentication headers for API requests"""
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'OfflineMode/1.0'
    }

def get_bookmarks(headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """Fetch bookmarks from Raindrop.io API with error handling and pagination"""
    try:
        url = 'https://api.raindrop.io/rest/v1/raindrops/0'
        all_bookmarks = []
        page = 0
        per_page = 50  # API default
        
        while True:
            params = {
                'page': page,
                'perpage': per_page
            }
            
            logger.debug(f"Fetching bookmarks page {page}")
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                bookmarks = data.get('items', [])
                
                if not bookmarks:
                    break  # No more bookmarks
                
                all_bookmarks.extend(bookmarks)
                
                # Check if we got fewer than per_page (last page)
                if len(bookmarks) < per_page:
                    break
                    
                page += 1
                
                # Add small delay between API calls
                time.sleep(0.1)
                
            elif response.status_code == 401:
                logger.error("Authentication failed - check your API token")
                break
            elif response.status_code == 429:
                logger.warning("Rate limit exceeded, waiting...")
                time.sleep(60)  # Wait 1 minute for rate limit reset
                continue
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                break
        
        logger.info(f"Retrieved {len(all_bookmarks)} total bookmarks from API")
        return all_bookmarks
        
    except requests.exceptions.Timeout:
        logger.error("API request timed out")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching bookmarks: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching bookmarks: {e}")
        return []

def verify_directory_structure(path: str) -> str:
    """Ensure the required directory structure exists and return the verified path"""
    try:
        # Check if we're already in an Offline Mode folder (case insensitive)
        if os.path.basename(path).lower() != "offline mode":
            # If not, look for one in the given path (case insensitive)
            for dirname in os.listdir(path):
                if dirname.lower() == "offline mode":
                    path = os.path.join(path, dirname)
                    break
            else:
                # Create new Offline Mode folder if none exists
                path = os.path.join(path, "Offline Mode")
                os.makedirs(path, exist_ok=True)

        # Create subdirectories
        os.makedirs(os.path.join(path, "article"), exist_ok=True)
        os.makedirs(os.path.join(path, "video"), exist_ok=True)

        logger.info(f"Directory structure verified at: {path}")
        return path

    except Exception as e:
        logger.error(f"Directory verification failed: {e}")
        raise


# Better solution: Enhanced archive function with proper title tracking
def _archive_removed_bookmarks_enhanced(path: str, current_bookmarks: List[Dict[str, Any]]) -> None:
    """
    Enhanced archive function that properly tracks online bookmarks vs local files
    
    Args:
        path: Local storage path
        current_bookmarks: List of current bookmarks from API
    """
    try:
        archive_dir = os.path.join(path, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        
        # Create subdirectories in archive
        os.makedirs(os.path.join(archive_dir, "article"), exist_ok=True)
        os.makedirs(os.path.join(archive_dir, "video"), exist_ok=True)
        
        # Create sets of current online bookmark titles (sanitized)
        current_online_titles = set()
        for bookmark in current_bookmarks:
            title = bookmark.get('title', 'Untitled')
            sanitized_title = web.sanitize_filename(title)
            current_online_titles.add(sanitized_title)
        
        archived_count = 0
        
        # Archive articles
        article_dir = os.path.join(path, "article")
        if os.path.exists(article_dir):
            for filename in os.listdir(article_dir):
                if filename.endswith('.html'):
                    title_from_file = filename[:-5]  # Remove .html extension
                    
                    # If this local file's title is not in current online bookmarks, archive it
                    if title_from_file not in current_online_titles:
                        src = os.path.join(article_dir, filename)
                        dest = os.path.join(archive_dir, "article", filename)
                        try:
                            if not os.path.exists(dest):  # Don't overwrite existing archived files
                                os.rename(src, dest)
                                logger.info(f"Archived removed article: {filename}")
                                archived_count += 1
                        except Exception as e:
                            logger.error(f"Failed to archive article {filename}: {e}")
        
        # Archive videos
        video_dir = os.path.join(path, "video")
        if os.path.exists(video_dir):
            for filename in os.listdir(video_dir):
                if filename.endswith('.mp4'):
                    title_from_file = filename[:-4]  # Remove .mp4 extension
                    
                    # If this local file's title is not in current online bookmarks, archive it
                    if title_from_file not in current_online_titles:
                        src = os.path.join(video_dir, filename)
                        dest = os.path.join(archive_dir, "video", filename)
                        try:
                            if not os.path.exists(dest):  # Don't overwrite existing archived files
                                os.rename(src, dest)
                                logger.info(f"Archived removed video: {filename}")
                                archived_count += 1
                        except Exception as e:
                            logger.error(f"Failed to archive video {filename}: {e}")
        
        if archived_count > 0:
            logger.info(f"Archived {archived_count} files that are no longer online")
        else:
            logger.info("No files needed archiving")
                            
    except Exception as e:
        logger.error(f"Error during archive process: {e}")

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    token = "114555b6-e18f-4ad3-bd50-055294f881a6"
    path = r"C:\Mina Maged\Offline Mode"
    resolution = "720"
    delimiter = "#$@"
    VIDEO = False
    
    # Create stop event for testing
    stop_event = threading.Event()
    
    # Run sync
    success = sync(token, path, resolution, delimiter, VIDEO, stop_event)
    
    if success:
        print("Sync completed successfully!")
    else:
        print("Sync failed or was cancelled")