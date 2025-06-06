import requests
import os
import re
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import base64
import mimetypes
import logging

logger = logging.getLogger(__name__)

def save_monolith(url, folder_path, file_name="saved_page"):
    """
    Self-contained web page saver that doesn't rely on external monolith command
    Downloads and embeds all resources (CSS, JS, images) into a single HTML file
    """
    file_name = sanitize_filename(file_name)
    try:
        os.makedirs(folder_path, exist_ok=True)
        target_path = os.path.join(folder_path, f"{file_name}.html")

        # Skip if file already exists and is recent
        if os.path.exists(target_path) and (time.time() - os.path.getmtime(target_path)) < 86400:
            logger.info(f"Skipping {url} - already exists")
            return

        # Create session with proper headers
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        # Download main HTML
        logger.info(f"Downloading: {url}")
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Process and embed resources
        _embed_css(soup, session, url)
        _embed_images(soup, session, url)
        _embed_javascript(soup, session, url)
        _clean_html(soup)
        
        # Save the processed HTML
        with open(target_path, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(str(soup))
            
        logger.info(f"Successfully saved: {file_name}.html")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error downloading {url}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error saving {url}: {e}")
        raise

def _embed_css(soup, session, base_url):
    """Embed CSS stylesheets into the HTML"""
    try:
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href')
            if not href:
                continue
                
            try:
                css_url = urljoin(base_url, href)
                response = session.get(css_url, timeout=15)
                response.raise_for_status()
                
                # Create style tag with embedded CSS
                style_tag = soup.new_tag('style')
                style_tag.string = response.text
                link.replace_with(style_tag)
                
            except Exception as e:
                logger.warning(f"Failed to embed CSS {href}: {e}")
                # Remove the link if we can't embed it
                link.decompose()
                
    except Exception as e:
        logger.error(f"Error processing CSS: {e}")

def _embed_images(soup, session, base_url):
    """Embed images as base64 data URLs"""
    try:
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src or src.startswith('data:'):
                continue
                
            try:
                img_url = urljoin(base_url, src)
                response = session.get(img_url, timeout=15)
                response.raise_for_status()
                
                # Determine content type
                content_type = response.headers.get('content-type', 'image/png')
                if not content_type.startswith('image/'):
                    # Guess from URL extension
                    ext = os.path.splitext(urlparse(img_url).path)[1].lower()
                    content_type = mimetypes.guess_type(f"file{ext}")[0] or 'image/png'
                
                # Convert to base64
                img_b64 = base64.b64encode(response.content).decode('utf-8')
                data_url = f"data:{content_type};base64,{img_b64}"
                img['src'] = data_url
                
            except Exception as e:
                logger.warning(f"Failed to embed image {src}: {e}")
                # Remove broken images
                img.decompose()
                
    except Exception as e:
        logger.error(f"Error processing images: {e}")

def _embed_javascript(soup, session, base_url):
    """Embed external JavaScript files"""
    try:
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if not src:
                continue
                
            try:
                js_url = urljoin(base_url, src)
                response = session.get(js_url, timeout=15)
                response.raise_for_status()
                
                # Create new script tag with embedded JS
                new_script = soup.new_tag('script')
                new_script.string = response.text
                script.replace_with(new_script)
                
            except Exception as e:
                logger.warning(f"Failed to embed JavaScript {src}: {e}")
                # Remove the script if we can't embed it
                script.decompose()
                
    except Exception as e:
        logger.error(f"Error processing JavaScript: {e}")

def _clean_html(soup):
    """Clean up the HTML and remove unnecessary elements"""
    try:
        # Remove problematic elements that might cause issues
        for element in soup.find_all(['script']):
            # Only remove scripts that might cause navigation or popups
            script_content = element.string or ''
            if any(keyword in script_content.lower() for keyword in 
                   ['window.location', 'document.location', 'location.href', 'history.', 'window.open']):
                element.decompose()
        
        # Remove meta refresh tags
        for meta in soup.find_all('meta', attrs={'http-equiv': 'refresh'}):
            meta.decompose()
            
        # Add meta tag to indicate this is an offline copy
        head = soup.find('head')
        if head:
            offline_meta = soup.new_tag('meta', attrs={
                'name': 'offline-copy',
                'content': f'Saved on {time.strftime("%Y-%m-%d %H:%M:%S")}'
            })
            head.insert(0, offline_meta)
            
    except Exception as e:
        logger.error(f"Error cleaning HTML: {e}")

def sanitize_filename(name):
    """Sanitize filename for Windows compatibility"""
    # Remove or replace invalid characters
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Remove leading/trailing spaces and dots
    name = name.strip('. ')
    # Limit length
    if len(name) > 200:
        name = name[:200]
    # Ensure it's not empty
    if not name:
        name = "untitled"
    return name

# Fallback function if requests/BeautifulSoup fail
def save_simple_html(url, folder_path, file_name="saved_page"):
    """Simple fallback that just saves the raw HTML without embedding resources"""
    file_name = sanitize_filename(file_name)
    try:
        os.makedirs(folder_path, exist_ok=True)
        target_path = os.path.join(folder_path, f"{file_name}.html")
        
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        with open(target_path, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(response.text)
            
        logger.info(f"Saved simple HTML: {file_name}.html")
        
    except Exception as e:
        logger.error(f"Failed to save simple HTML for {url}: {e}")
        raise

# Example usage
if __name__ == "__main__":
    try:
        save_monolith(
            url="https://example.com",
            folder_path=r"C:\test",
            file_name="example_page"
        )
    except Exception as e:
        print(f"Error: {e}")