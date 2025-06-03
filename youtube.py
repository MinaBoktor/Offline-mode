import os
import sys
import subprocess
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def get_bundled_yt_dlp_path():
    """Get the path to bundled yt-dlp executable"""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        bundle_dir = sys._MEIPASS
        yt_dlp_path = os.path.join(bundle_dir, 'yt-dlp.exe')
    else:
        # Running as script - look for yt-dlp in same directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        yt_dlp_path = os.path.join(script_dir, 'yt-dlp.exe')
    
    return yt_dlp_path if os.path.exists(yt_dlp_path) else None

def download_yt_dlp():
    """Download yt-dlp executable if not present"""
    try:
        import requests
        
        # Determine where to save yt-dlp
        if getattr(sys, 'frozen', False):
            # Can't write to _MEIPASS, use temp directory
            yt_dlp_dir = tempfile.gettempdir()
        else:
            # Save in script directory
            yt_dlp_dir = os.path.dirname(os.path.abspath(__file__))
        
        yt_dlp_path = os.path.join(yt_dlp_dir, 'yt-dlp.exe')
        
        if os.path.exists(yt_dlp_path):
            return yt_dlp_path
        
        logger.info("Downloading yt-dlp...")
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        with open(yt_dlp_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Downloaded yt-dlp to {yt_dlp_path}")
        return yt_dlp_path
        
    except Exception as e:
        logger.error(f"Failed to download yt-dlp: {e}")
        return None

def save(url='', output_path='.', resolution='720'):
    """
    Save video using yt-dlp with fallback mechanisms
    """
    if not url:
        logger.error("No URL provided")
        return False
    
    try:
        os.makedirs(output_path, exist_ok=True)
        
        # Method 1: Try using yt-dlp Python library
        success = _save_with_library(url, output_path, resolution)
        if success:
            return True
        
        # Method 2: Try using bundled yt-dlp executable
        success = _save_with_executable(url, output_path, resolution)
        if success:
            return True
        
        # Method 3: Try downloading yt-dlp and using it
        success = _save_with_downloaded_executable(url, output_path, resolution)
        if success:
            return True
        
        logger.error("All video download methods failed")
        return False
        
    except Exception as e:
        logger.error(f"Error in video save: {e}")
        return False

def _save_with_library(url, output_path, resolution):
    """Try using yt-dlp Python library"""
    try:
        import yt_dlp
        
        ydl_opts = {
            'format': f'bestvideo[height<={resolution}][ext=mp4]+bestaudio[ext=m4a]/best[height<={resolution}]',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        logger.info("Successfully downloaded video using yt-dlp library")
        return True
        
    except ImportError:
        logger.warning("yt-dlp library not available")
        return False
    except Exception as e:
        logger.error(f"Library download failed: {e}")
        return False

def _save_with_executable(url, output_path, resolution):
    """Try using bundled yt-dlp executable"""
    try:
        yt_dlp_path = get_bundled_yt_dlp_path()
        if not yt_dlp_path:
            return False
        
        return _run_yt_dlp_executable(yt_dlp_path, url, output_path, resolution)
        
    except Exception as e:
        logger.error(f"Executable download failed: {e}")
        return False

def _save_with_downloaded_executable(url, output_path, resolution):
    """Try downloading yt-dlp executable and using it"""
    try:
        yt_dlp_path = download_yt_dlp()
        if not yt_dlp_path:
            return False
        
        return _run_yt_dlp_executable(yt_dlp_path, url, output_path, resolution)
        
    except Exception as e:
        logger.error(f"Downloaded executable failed: {e}")
        return False

def _run_yt_dlp_executable(yt_dlp_path, url, output_path, resolution):
    """Run yt-dlp executable with given parameters"""
    try:
        # Create output template
        output_template = os.path.join(output_path, '%(title)s.%(ext)s')
        
        # Build command
        cmd = [
            yt_dlp_path,
            '--format', f'bestvideo[height<={resolution}][ext=mp4]+bestaudio[ext=m4a]/best[height<={resolution}]',
            '--merge-output-format', 'mp4',
            '--output', output_template,
            '--quiet',
            '--no-warnings',
            '--no-playlist',
            url
        ]
        
        # Configure subprocess to hide window
        startupinfo = None
        if os.name == 'nt':  # Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        
        # Run command with timeout
        result = subprocess.run(
            cmd,
            timeout=300,  # 5 minute timeout
            capture_output=False,
            startupinfo=startupinfo,
            check=True
        )
        
        logger.info("Successfully downloaded video using yt-dlp executable")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("Video download timed out")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp executable failed with return code {e.returncode}")
        return False
    except Exception as e:
        logger.error(f"Executable run failed: {e}")
        return False

def get_video_info(url):
    """Get video information without downloading"""
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'description': info.get('description', ''),
            }
    except Exception as e:
        logger.error(f"Failed to get video info: {e}")
        return None

def is_video_url(url):
    """Check if URL is likely a video URL"""
    video_domains = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
        'twitch.tv', 'facebook.com', 'instagram.com', 'twitter.com',
        'tiktok.com', 'reddit.com'
    ]
    
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        return any(video_domain in domain for video_domain in video_domains)
    except:
        return False

# Compatibility function to maintain API
def download_video(url, output_path, resolution='720'):
    """Legacy function name for compatibility"""
    return save(url, output_path, resolution)

if __name__ == "__main__":
    # Test the video downloader
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    test_output = "./test_videos"
    
    print("Testing video download...")
    success = save(test_url, test_output, '720')
    print(f"Download {'succeeded' if success else 'failed'}")