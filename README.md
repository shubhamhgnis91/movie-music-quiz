# Movie Music Quiz

A real-time multiplayer quiz game where players guess movie titles from their soundtracks.

## Features

- Create and join quiz rooms with optional passwords
- Real-time multiplayer gameplay via WebSocket
- Music streaming from movie soundtracks
- Live scoring and leaderboards
- Chat functionality during games

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
uvicorn main:app --reload --port 8000
```

4. Open your browser to `http://localhost:8000`

## How to Play

1. Enter your name and create a room or join an existing one
2. Wait for all players to mark themselves as ready
3. Listen to music clips and guess the movie title
4. Score points for correct guesses
5. Winner is announced after all rounds complete

## Tech Stack

- **Backend**: FastAPI, WebSockets, SQLite
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Music**: JioSaavn API integration
