"""
Music service for fetching songs from JioSaavn API.
Handles external API integration and song data processing.
"""
import random
from typing import Dict, List, Optional
import httpx
from app.config import settings
from app.services.validation import sanitize_text_input, validate_url
from app.database.db_manager import get_random_movie_title


async def search_jiosaavn(term: str) -> List[Dict]:
    """
    Search for songs on JioSaavn by movie/album name.
    
    Args:
        term: Search term (movie/album name)
        
    Returns:
        List of song dictionaries
    """
    # Sanitize search term
    term = sanitize_text_input(term)
    if not term:
        return []
    
    async with httpx.AsyncClient() as client:
        search_params = {"query": term, "limit": 1}
        try:
            search_response = await client.get(settings.JIOSAAVN_SEARCH_URL, params=search_params, timeout=10.0)
            search_data = search_response.json()
        except Exception as e:
            print(f"Error searching JioSaavn: {str(e)[:100]}...")
            return []
        
        if not search_data.get("data", {}).get("results"):
            return []
        
        album_id = search_data["data"]["results"][0].get("id")
        if not album_id:
            return []
        
        album_params = {"id": album_id}
        try:
            album_response = await client.get(settings.JIOSAAVN_ALBUM_URL, params=album_params, timeout=10.0)
            album_data = album_response.json()
        except Exception as e:
            print(f"Error fetching album from JioSaavn: {str(e)[:100]}...")
            return []
        
        return album_data.get("data", {}).get("songs", [])


async def get_quiz_song() -> Dict:
    """
    Get a random quiz song with metadata.
    
    Returns:
        Dictionary with song metadata (title, movie, preview_url, image)
    """
    # Try to get from database first
    try:
        movie_title = get_random_movie_title()
        
        if not movie_title:
            print("⚠️  No movie title from database, using demo song")
            return settings.DEMO_SONG.copy()
        
        print(f"🎬 Searching for songs from: {movie_title}")
        songs = await search_jiosaavn(movie_title)
        
        if not songs:
            print(f"⚠️  No songs found for '{movie_title}', using demo song")
            return settings.DEMO_SONG.copy()
            
        chosen_song = random.choice(songs)
        best_url = ""
        album_image = ""
        
        # Get the best quality audio URL
        for link in chosen_song.get("downloadUrl", []):
            if link.get("quality") == "320kbps":
                best_url = link.get("url")
                break
        
        # Validate URLs before using
        if best_url and not validate_url(best_url):
            best_url = ""
        
        # Get album image
        for img in chosen_song.get("image", []):
            if img.get("quality") == "500x500":
                album_image = img.get("url")
                break
        
        if album_image and not validate_url(album_image):
            album_image = ""
        
        # If no best URL found, use any available
        if not best_url and chosen_song.get("downloadUrl"):
            best_url = chosen_song["downloadUrl"][0].get("url", "")
            if not validate_url(best_url):
                best_url = ""
        
        # Use first image if 500x500 not found
        if not album_image and chosen_song.get("image"):
            album_image = chosen_song["image"][0].get("url", "")
            if not validate_url(album_image):
                album_image = ""
        
        if best_url:
            song_title = sanitize_text_input(chosen_song.get("name", "Unknown"))
            print(f"✅ Found song: '{song_title}' from '{movie_title}'")
            return {
                "title": song_title,
                "movie": sanitize_text_input(movie_title),
                "preview_url": best_url,
                "image": album_image or "https://via.placeholder.com/300x300?text=No+Image"
            }
        else:
            print(f"⚠️  No valid audio URL found for '{movie_title}', using demo song")
    except Exception as e:
        print(f"❌ Error getting quiz song: {str(e)[:100]}")
    
    # Return demo song if database fails or no songs found
    print("🎵 Using demo song as fallback")
    return settings.DEMO_SONG.copy()
