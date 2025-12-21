"""
YouTube Data API Service for fetching channel videos and shorts
"""
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def get_api_key():
    """Get YouTube API key from environment"""
    return os.environ.get('YOUTUBE_API_KEY')


def get_channel_id():
    """Get YouTube channel ID from environment"""
    return os.environ.get('YOUTUBE_CHANNEL_ID')


def parse_duration(duration_str):
    """Parse ISO 8601 duration to human readable format (e.g., PT1H30M45S -> 1:30:45)"""
    if not duration_str:
        return None
    
    duration_str = duration_str.replace('PT', '')
    hours = 0
    minutes = 0
    seconds = 0
    
    if 'H' in duration_str:
        hours, duration_str = duration_str.split('H')
        hours = int(hours)
    if 'M' in duration_str:
        minutes, duration_str = duration_str.split('M')
        minutes = int(minutes)
    if 'S' in duration_str:
        seconds = int(duration_str.replace('S', ''))
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


def get_duration_seconds(duration_str):
    """Parse ISO 8601 duration to seconds"""
    if not duration_str:
        return 0
    
    duration_str = duration_str.replace('PT', '')
    hours = 0
    minutes = 0
    seconds = 0
    
    if 'H' in duration_str:
        hours, duration_str = duration_str.split('H')
        hours = int(hours)
    if 'M' in duration_str:
        minutes, duration_str = duration_str.split('M')
        minutes = int(minutes)
    if 'S' in duration_str:
        seconds = int(duration_str.replace('S', ''))
    
    return hours * 3600 + minutes * 60 + seconds


def is_youtube_short(video_id):
    """
    Check if a video is a YouTube Short by making a HEAD request.
    Returns True if it's a short, False otherwise.
    """
    try:
        url = f'https://www.youtube.com/shorts/{video_id}'
        response = requests.head(url, allow_redirects=False, timeout=5)
        # If status is 200 and no redirect, it's a short
        return response.status_code == 200
    except:
        return False


def get_shorts_playlist_id(channel_id):
    """
    Convert channel ID to shorts playlist ID.
    Replace 'UC' prefix with 'UUSH' to get the shorts playlist.
    """
    if channel_id.startswith('UC'):
        return 'UUSH' + channel_id[2:]
    return None


def get_videos_playlist_id(channel_id):
    """
    Convert channel ID to regular videos playlist ID.
    Replace 'UC' prefix with 'UULF' to get regular videos only.
    """
    if channel_id.startswith('UC'):
        return 'UULF' + channel_id[2:]
    return None


def fetch_playlist_videos(playlist_id, max_results=50):
    """Fetch videos from a specific playlist"""
    api_key = get_api_key()
    
    if not api_key:
        return [], "YouTube API key not configured."
    
    if not playlist_id:
        return [], "Invalid playlist ID."
    
    try:
        # Fetch videos from playlist
        videos_url = f"{YOUTUBE_API_BASE}/playlistItems"
        videos_params = {
            'key': api_key,
            'playlistId': playlist_id,
            'part': 'snippet',
            'maxResults': min(max_results, 50)
        }
        
        response = requests.get(videos_url, params=videos_params, timeout=10)
        
        if response.status_code == 404:
            return [], None  # Playlist doesn't exist (no shorts/videos)
        
        response.raise_for_status()
        playlist_data = response.json()
        
        if not playlist_data.get('items'):
            return [], None
        
        # Get video IDs for fetching duration
        video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_data['items']]
        
        # Fetch video details
        details_url = f"{YOUTUBE_API_BASE}/videos"
        details_params = {
            'key': api_key,
            'id': ','.join(video_ids),
            'part': 'contentDetails,snippet,statistics'
        }
        
        response = requests.get(details_url, params=details_params, timeout=10)
        response.raise_for_status()
        details_data = response.json()
        
        videos = []
        for item in details_data.get('items', []):
            video_id = item['id']
            snippet = item['snippet']
            content_details = item['contentDetails']
            statistics = item.get('statistics', {})
            
            duration_str = content_details.get('duration', '')
            
            # Parse published date
            published_at = snippet.get('publishedAt', '')
            if published_at:
                try:
                    published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                except:
                    published_date = datetime.utcnow()
            else:
                published_date = datetime.utcnow()
            
            video_data = {
                'video_id': video_id,
                'title': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', 
                                 snippet.get('thumbnails', {}).get('medium', {}).get('url', '')),
                'duration': parse_duration(duration_str),
                'duration_seconds': get_duration_seconds(duration_str),
                'published_at': published_date,
                'view_count': int(statistics.get('viewCount', 0)),
            }
            videos.append(video_data)
        
        return videos, None
        
    except requests.exceptions.RequestException as e:
        return [], f"Failed to fetch videos: {str(e)}"
    except Exception as e:
        return [], f"Error processing videos: {str(e)}"


def fetch_channel_videos(max_results=50):
    """
    Fetch videos from a YouTube channel.
    Uses separate playlists for regular videos (UULF) and shorts (UUSH).
    Returns a tuple: (videos_list, shorts_list, error_message)
    """
    api_key = get_api_key()
    channel_id = get_channel_id()
    
    if not api_key:
        return [], [], "YouTube API key not configured. Set YOUTUBE_API_KEY in your environment."
    
    if not channel_id:
        return [], [], "YouTube channel ID not configured. Set YOUTUBE_CHANNEL_ID in your environment."
    
    videos = []
    shorts = []
    errors = []
    
    # Fetch regular videos using UULF playlist
    videos_playlist_id = get_videos_playlist_id(channel_id)
    if videos_playlist_id:
        fetched_videos, error = fetch_playlist_videos(videos_playlist_id, max_results)
        if error:
            errors.append(f"Videos: {error}")
        else:
            videos = fetched_videos
    
    # Fetch shorts using UUSH playlist
    shorts_playlist_id = get_shorts_playlist_id(channel_id)
    if shorts_playlist_id:
        fetched_shorts, error = fetch_playlist_videos(shorts_playlist_id, max_results)
        if error:
            errors.append(f"Shorts: {error}")
        else:
            shorts = fetched_shorts
    
    # If both failed, try the fallback method
    if not videos and not shorts and errors:
        return fetch_channel_videos_fallback(max_results)
    
    error_msg = "; ".join(errors) if errors else None
    return videos, shorts, error_msg


def fetch_channel_videos_fallback(max_results=50):
    """
    Fallback method: Fetch all videos and use HEAD request to detect shorts.
    This is slower but works if the UULF/UUSH playlists don't exist.
    """
    api_key = get_api_key()
    channel_id = get_channel_id()
    
    try:
        # Get the uploads playlist ID
        channel_url = f"{YOUTUBE_API_BASE}/channels"
        channel_params = {
            'key': api_key,
            'id': channel_id,
            'part': 'contentDetails'
        }
        
        response = requests.get(channel_url, params=channel_params, timeout=10)
        response.raise_for_status()
        channel_data = response.json()
        
        if not channel_data.get('items'):
            return [], [], "Channel not found. Check your YOUTUBE_CHANNEL_ID."
        
        uploads_playlist_id = channel_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Fetch all videos from uploads
        all_videos, error = fetch_playlist_videos(uploads_playlist_id, max_results)
        
        if error:
            return [], [], error
        
        # Separate shorts from regular videos using HEAD request
        videos = []
        shorts = []
        
        for video in all_videos:
            if is_youtube_short(video['video_id']):
                shorts.append(video)
            else:
                videos.append(video)
        
        return videos, shorts, None
        
    except Exception as e:
        return [], [], f"Error: {str(e)}"


def fetch_shorts_only(max_results=50):
    """Fetch only shorts from a YouTube channel"""
    channel_id = get_channel_id()
    
    if not channel_id:
        return [], "YouTube channel ID not configured."
    
    shorts_playlist_id = get_shorts_playlist_id(channel_id)
    if shorts_playlist_id:
        return fetch_playlist_videos(shorts_playlist_id, max_results)
    
    return [], "Could not generate shorts playlist ID."


def fetch_videos_only(max_results=50):
    """Fetch only regular videos (not shorts) from a YouTube channel"""
    channel_id = get_channel_id()
    
    if not channel_id:
        return [], "YouTube channel ID not configured."
    
    videos_playlist_id = get_videos_playlist_id(channel_id)
    if videos_playlist_id:
        return fetch_playlist_videos(videos_playlist_id, max_results)
    
    return [], "Could not generate videos playlist ID."


def fetch_single_video(video_id):
    """Fetch details for a single video by ID"""
    api_key = get_api_key()
    
    if not api_key:
        return None, "YouTube API key not configured."
    
    try:
        details_url = f"{YOUTUBE_API_BASE}/videos"
        details_params = {
            'key': api_key,
            'id': video_id,
            'part': 'contentDetails,snippet,statistics'
        }
        
        response = requests.get(details_url, params=details_params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('items'):
            return None, "Video not found."
        
        item = data['items'][0]
        snippet = item['snippet']
        content_details = item['contentDetails']
        statistics = item.get('statistics', {})
        
        duration_str = content_details.get('duration', '')
        
        return {
            'video_id': video_id,
            'title': snippet.get('title', ''),
            'description': snippet.get('description', ''),
            'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            'duration': parse_duration(duration_str),
            'duration_seconds': get_duration_seconds(duration_str),
            'view_count': int(statistics.get('viewCount', 0)),
            'is_short': is_youtube_short(video_id)
        }, None
        
    except Exception as e:
        return None, str(e)


def fetch_channel_statistics():
    """
    Fetch channel statistics including subscriber count and total views.
    Returns a dict with subscriber_count, view_count, video_count or None on error.
    """
    api_key = get_api_key()
    channel_id = get_channel_id()
    
    if not api_key:
        return None, "YouTube API key not configured."
    
    if not channel_id:
        return None, "YouTube channel ID not configured."
    
    try:
        channel_url = f"{YOUTUBE_API_BASE}/channels"
        channel_params = {
            'key': api_key,
            'id': channel_id,
            'part': 'statistics,snippet'
        }
        
        response = requests.get(channel_url, params=channel_params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('items'):
            return None, "Channel not found."
        
        stats = data['items'][0].get('statistics', {})
        snippet = data['items'][0].get('snippet', {})
        
        return {
            'subscriber_count': int(stats.get('subscriberCount', 0)),
            'view_count': int(stats.get('viewCount', 0)),
            'video_count': int(stats.get('videoCount', 0)),
            'channel_title': snippet.get('title', ''),
            'channel_description': snippet.get('description', ''),
            'hidden_subscriber_count': stats.get('hiddenSubscriberCount', False)
        }, None
        
    except Exception as e:
        return None, f"Error fetching channel stats: {str(e)}"