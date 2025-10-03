"""
Database operations and initialization.
Handles SQLite database setup and query operations.
"""
import csv
import sqlite3
from typing import List, Optional
from app.config import settings
from app.services.validation import sanitize_text_input, escape_sql_like_pattern


def initialize_database() -> None:
    """Initialize the database with movie data on startup."""
    try:
        connection = sqlite3.connect(settings.DB_PATH)
        cursor = connection.cursor()
        
        # Check if table exists and has data
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='movies'")
        table_exists = cursor.fetchone()[0] > 0
        
        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM movies")
            movie_count = cursor.fetchone()[0]
            if movie_count > 0:
                print(f"Database already initialized with {movie_count} movies.")
                connection.close()
                return
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE
            )
        """)
        
        print("Initializing database with movie data...")
        
        # Try to read from CSV file first
        movies_added = 0
        try:
            with open('top500.csv', 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    title = row.get('Movie', '').strip()
                    if title and len(title) <= settings.MAX_MOVIE_TITLE_LENGTH:
                        try:
                            cursor.execute("INSERT INTO movies (title) VALUES (?)", (title,))
                            movies_added += 1
                        except sqlite3.IntegrityError:
                            pass  # Skip duplicates
            
            print(f"Added {movies_added} movies from top500.csv")
            
        except FileNotFoundError:
            # Fallback: add some demo movies
            print("top500.csv not found. Adding demo movies...")
            demo_movies = [
                "3 Idiots", "Dangal", "PK", "Baahubali", "KGF",
                "Kabir Singh", "Dilwale Dulhania Le Jayenge", "Sholay",
                "Mughal-e-Azam", "Mother India", "Lagaan", "Taare Zameen Par",
                "Rang De Basanti", "Swades", "Zindagi Na Milegi Dobara"
            ]
            
            for title in demo_movies:
                try:
                    cursor.execute("INSERT INTO movies (title) VALUES (?)", (title,))
                    movies_added += 1
                except sqlite3.IntegrityError:
                    pass
            
            print(f"Added {movies_added} demo movies")
        
        connection.commit()
        connection.close()
        print("Database initialization completed successfully!")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        # Continue without database - the app will use demo songs


def get_random_movie_title() -> Optional[str]:
    """
    Get a random movie title from the database.
    
    Returns:
        Random movie title or None if database is empty
    """
    try:
        connection = sqlite3.connect(settings.DB_PATH)
        cursor = connection.cursor()
        cursor.execute("SELECT title FROM movies ORDER BY RANDOM() LIMIT 1")
        result = cursor.fetchone()
        connection.close()
        
        if result:
            return sanitize_text_input(result[0])
        return None
    except Exception as e:
        print(f"Database error: {str(e)[:100]}...")
        return None


async def get_movie_suggestions(query: str) -> List[str]:
    """
    Get movie title suggestions from database for autocomplete.
    
    Args:
        query: Search query
        
    Returns:
        List of matching movie titles (max 10)
    """
    # Sanitize and validate input
    query = sanitize_text_input(query)
    if not query or len(query) < settings.MIN_SUGGESTION_QUERY_LENGTH or len(query) > settings.MAX_SUGGESTION_QUERY_LENGTH:
        return []
    
    try:
        connection = sqlite3.connect(settings.DB_PATH)
        cursor = connection.cursor()
        
        # Escape special SQL LIKE wildcards
        escaped_query = escape_sql_like_pattern(query)
        search_pattern = f"%{escaped_query}%"
        
        cursor.execute(
            "SELECT DISTINCT title FROM movies WHERE LOWER(title) LIKE LOWER(?) ESCAPE '\\' LIMIT 10",
            (search_pattern,)
        )
        results = cursor.fetchall()
        connection.close()
        
        return [sanitize_text_input(result[0]) for result in results]
    except Exception as e:
        print(f"Error getting suggestions: {str(e)[:100]}...")
        return []
