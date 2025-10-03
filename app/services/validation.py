"""
Input validation and sanitization utilities.
Security-focused validation functions for user inputs.
"""
import re
from app.config import settings


def sanitize_text_input(text: str) -> str:
    """
    Sanitize text input to prevent XSS and injection attacks.
    
    Args:
        text: Raw user input text
        
    Returns:
        Sanitized text safe for display
    """
    if not text:
        return ""
    
    # Remove/escape potentially dangerous characters
    text = str(text).strip()
    
    # Remove HTML tags and scripts
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    # Limit length to prevent DoS
    text = text[:settings.MAX_TEXT_INPUT_LENGTH] if text else ""
    
    return text


def validate_room_id(room_id: str) -> bool:
    """
    Validate room ID format.
    
    Args:
        room_id: Room ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    return bool(room_id and re.match(r'^[A-Z0-9]{6}$', room_id))


def validate_client_id(client_id: int) -> bool:
    """
    Validate client ID range.
    
    Args:
        client_id: Client ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    return isinstance(client_id, int) and 10000 <= client_id <= 99999


def validate_url(url: str) -> bool:
    """
    Validate URL format (must start with http:// or https://).
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
    return url.startswith(('http://', 'https://'))


def escape_sql_like_pattern(pattern: str) -> str:
    """
    Escape special SQL LIKE wildcards (% and _).
    
    Args:
        pattern: SQL LIKE pattern
        
    Returns:
        Escaped pattern
    """
    return pattern.replace('%', '\\%').replace('_', '\\_')
