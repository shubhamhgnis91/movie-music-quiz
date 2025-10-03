"""
Security middleware for the application.
Implements security headers, rate limiting, and other security features.
"""
from collections import defaultdict, deque
from datetime import datetime, timedelta
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all HTTP responses."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Enable XSS filter in older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Enforce HTTPS
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy
        # Allows the app to work with external APIs while blocking unwanted scripts
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "media-src 'self' https:; "
            "connect-src 'self' wss: https://saavn.dev;"
        )
        
        return response


class RateLimitManager:
    """Manages rate limiting for API requests."""
    
    def __init__(self):
        self.storage = defaultdict(lambda: deque())
        self.connection_count = defaultdict(int)
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """
        Check if client has exceeded rate limit.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            True if within limit, False if exceeded
        """
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old requests
        while self.storage[client_ip] and self.storage[client_ip][0] < minute_ago:
            self.storage[client_ip].popleft()
        
        # Check if under limit
        if len(self.storage[client_ip]) >= settings.MAX_REQUESTS_PER_MINUTE:
            return False
        
        # Add current request
        self.storage[client_ip].append(now)
        return True
    
    def increment_connection(self, client_ip: str) -> bool:
        """
        Increment connection count for an IP.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            True if within limit, False if exceeded
        """
        if self.connection_count[client_ip] >= settings.MAX_CONNECTIONS_PER_IP:
            return False
        self.connection_count[client_ip] += 1
        return True
    
    def decrement_connection(self, client_ip: str) -> None:
        """
        Decrement connection count for an IP.
        
        Args:
            client_ip: Client IP address
        """
        self.connection_count[client_ip] -= 1
        if self.connection_count[client_ip] <= 0:
            del self.connection_count[client_ip]


# Global rate limit manager instance
rate_limiter = RateLimitManager()
