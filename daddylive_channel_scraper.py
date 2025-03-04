#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import json
import time
import os
from urllib.parse import urljoin

# Configuration
BASE_URL = "https://daddylive.mp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# Categories to search for channels
CATEGORIES = [
    "sports",
    "entertainment",
    "news",
    "movies",
    "usa",
    "uk",
    "international"
]

def get_page_content(url):
    """Get the HTML content of a page with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retrying
            else:
                print(f"Failed to fetch {url} after {max_retries} attempts")
                return None

def extract_channel_numbers(html_content):
    """Extract channel numbers from HTML content using regex"""
    if not html_content:
        return []
    
    # Look for links with pattern stream-XXX.php
    pattern = r'href="[^"]*stream-(\d+)\.php"'
    matches = re.findall(pattern, html_content)
    return list(set(matches))  # Remove duplicates

def get_channel_info(channel_page_url, channel_number):
    """Extract channel information from its page"""
    html_content = get_page_content(channel_page_url)
    if not html_content:
        return None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try to get channel name
    title_elem = soup.select_one('h1.entry-title') or soup.select_one('title')
    if title_elem:
        title = title_elem.text.strip()
        # Clean up title
        title = re.sub(r'Watch\s+', '', title)
        title = re.sub(r'\s+Live Stream.*', '', title)
        title = title.strip()
    else:
        title = f"Channel {channel_number}"
    
    # Determine category based on URL or content
    category = "Uncategorized"
    for cat in CATEGORIES:
        if cat.lower() in channel_page_url.lower() or (title and cat.lower() in title.lower()):
            category = cat.capitalize()
            break

    # Some common channel mappings to improve metadata
    channel_mappings = {
        'espn': {'id': 'espn', 'logo': 'https://i.imgur.com/GhhN7RZ.png', 'category': 'Sports'},
        'espn2': {'id': 'espn2', 'logo': 'https://i.imgur.com/R7UtvMv.png', 'category': 'Sports'},
        'fox': {'id': 'fox', 'logo': 'https://i.imgur.com/5XuxwU2.png', 'category': 'Entertainment'},
        'cnn': {'id': 'cnn', 'logo': 'https://i.imgur.com/1JnyzHv.png', 'category': 'News'},
        'bbc': {'id': 'bbc', 'logo': 'https://i.imgur.com/UF9IfLw.png', 'category': 'News'},
        'nbc': {'id': 'nbc', 'logo': 'https://i.imgur.com/yPVJbpC.png', 'category': 'Entertainment'},
        'abc': {'id': 'abc', 'logo': 'https://i.imgur.com/UtqRX7U.png', 'category': 'Entertainment'},
        'hbo': {'id': 'hbo', 'logo': 'https://i.imgur.com/RQwVnBf.png', 'category': 'Movies'},
    }
    
    # Check if any known channel name is in the title
    channel_id = f"ch{channel_number}"
    logo_url = ""
    
    for key, info in channel_mappings.items():
        if key.lower() in title.lower():
            channel_id = info['id']
            logo_url = info['logo']
            if 'category' in info:
                category = info['category']
            break
            
    return {
        "id": channel_id,
        "name": title,
        "logo": logo_url,
        "category": category,
        "number": channel_number,
        "url": channel_page_url
    }

def scan_for_channels():
    """Scan DaddyLive for all available channels"""
    all_channels = []
    channel_numbers = set()
    
    # First approach: Scan the main page and category pages
    pages_to_scan = [BASE_URL]
    for category in CATEGORIES:
        pages_to_scan.append(f"{BASE_URL}/{category}")
    
    print("Scanning main pages for channel links...")
    for page_url in pages_to_scan:
        html_content = get_page_content(page_url)
        if html_content:
            numbers = extract_channel_numbers(html_content)
            channel_numbers.update(numbers)
    
    # Second approach: Try sequential numbers within a reasonable range
    # Start with numbers we've already found to determine a likely range
    if channel_numbers:
        min_number = min(int(n) for n in channel_numbers)
        max_number = max(int(n) for n in channel_numbers)
        
        # Extend the range slightly in both directions
        range_min = max(1, min_number - 50)
        range_max = max_number + 50
        
        print(f"Extending search to check channel numbers from {range_min} to {range_max}...")
        
        # Add these numbers to our search list
        for i in range(range_min, range_max + 1):
            channel_numbers.add(str(i))
    else:
        # If we didn't find any channels, try a broad range
        print("No channels found in initial scan. Trying a broad range...")
        for i in range(1, 1000):
            channel_numbers.add(str(i))
    
    # Get info for each channel number
    total = len(channel_numbers)
    for idx, number in enumerate(sorted(channel_numbers, key=int)):
        channel_url = f"{BASE_URL}/stream/stream-{number}.php"
        print(f"Processing {idx+1}/{total}: Channel {number}")
        
        channel_info = get_channel_info(channel_url, number)
        if channel_info:
            all_channels.append(channel_info)
            # Save progress periodically
            if idx % 10 == 0:
                save_channels(all_channels)
        
        # Be nice to the server
        time.sleep(1)
    
    # Final save
    save_channels(all_channels)
    return all_channels

def save_channels(channels, filename="daddylive_channels.json"):
    """Save channel information to a JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(channels, f, indent=2)
    print(f"Saved {len(channels)} channels to {filename}")

def generate_m3u_playlist(channels, output_file="daddylive_all_channels.m3u"):
    """Generate M3U playlist from channel list"""
    with open(output_file, "w", encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        
        for channel in channels:
            # Write channel info
            f.write(f'#EXTINF:-1 tvg-id="{channel["id"]}" tvg-name="{channel["name"]}" '
                   f'tvg-logo="{channel["logo"]}" group-title="{channel["category"]}",{channel["name"]}\n')
            
            # Write required headers as EXTVLCOPT
            f.write('#EXTVLCOPT:http-user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36\n')
            f.write('#EXTVLCOPT:http-referrer=https://cookiewebplay.xyz/\n')
            f.write('#EXTVLCOPT:http-origin=https://cookiewebplay.xyz\n')
            
            # Write stream URL
            f.write(f'https://ddy6new.iosplayer.ru/ddy6/premium{channel["number"]}/mono.m3u8\n\n')
    
    print(f"Playlist created successfully: {output_file}")

def main():
    if os.path.exists("daddylive_channels.json"):
        print("Found existing channel data, loading from file...")
        with open("daddylive_channels.json", 'r', encoding='utf-8') as f:
            channels = json.load(f)
    else:
        print("Scanning for all available channels...")
        channels = scan_for_channels()
    
    print(f"Found {len(channels)} channels")
    
    # Generate playlist
    generate_m3u_playlist(channels)
    print("\nAll done! You can now upload the playlist to your GitHub repository.")

if __name__ == "__main__":
    main()
