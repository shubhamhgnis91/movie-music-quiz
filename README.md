# Movie Music Quiz

A real-time multiplayer quiz game where players guess Bollywood movie titles from their soundtracks.

## 🎵 Features

- **Multiplayer Rooms**: Create and join quiz rooms with optional password protection
- **Real-time Gameplay**: Live WebSocket communication for instant updates
- **Music Streaming**: High-quality music from Bollywood soundtracks via JioSaavn API
- **Multiple Game Modes**: Regular and Speed modes with different scoring systems
- **Live Scoring**: Real-time leaderboards and score tracking
- **Chat System**: In-game chat for player communication
- **Movie Autocomplete**: Smart movie title suggestions while typing
- **Host Controls**: Kick players, adjust game settings, start games
- **Security First**: XSS protection, input validation, rate limiting, and comprehensive security headers

## 🏗️ Architecture

This application follows modern best practices with a clean, modular architecture:

```
movie-music-quiz/
├── main.py                    # Application entry point
├── app/
│   ├── config.py             # Configuration management
│   ├── database/             # Database operations
│   ├── models/               # Pydantic models & game state
│   ├── middleware/           # Security & CORS middleware
│   ├── routes/               # API & WebSocket endpoints
│   ├── services/             # Business logic services
│   └── utils/                # Utility functions
└── static/                   # Frontend assets
```

### Key Components

- **Routes**: Clean separation of API endpoints and WebSocket handlers
- **Services**: Reusable business logic (validation, game logic, music API)
- **Models**: Type-safe data models using Pydantic
- **Middleware**: Security headers, rate limiting, CORS
- **Database**: SQLite with 500+ Bollywood movies

## 🔐 Security Features

This application implements comprehensive security best practices:

- ✅ **Input Sanitization**: All user inputs sanitized to prevent XSS
- ✅ **SQL Injection Prevention**: Parameterized queries throughout
- ✅ **Secure Password Handling**: SHA-256 hashing with HMAC comparison
- ✅ **Rate Limiting**: 60 requests/minute per IP
- ✅ **Connection Limiting**: 5 concurrent connections per IP
- ✅ **Security Headers**:
  - Content-Security-Policy (CSP)
  - Strict-Transport-Security (HSTS)
  - X-Frame-Options: DENY
  - X-Content-Type-Options: nosniff
  - X-XSS-Protection
  - Referrer-Policy
- ✅ **DoS Protection**: Room limits, message size limits, automatic cleanup
- ✅ **CORS**: Restrictive origins (no wildcards)

See [SECURITY.md](SECURITY.md) for detailed security documentation.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables (Optional)

```bash
# Windows PowerShell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"

# Linux/Mac
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

*If not set, a secure key will be auto-generated (with a warning).*

### 3. Run the Server

```bash
# Development mode with auto-reload
uvicorn main:app --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. Access the Application

- **Homepage**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 🎮 How to Play

1. **Create or Join a Room**
   - Enter your name
   - Create a new room (optionally with password) or join an existing one

2. **Configure Game Settings** (Host only)
   - Number of rounds (5-20)
   - Music duration (15-60 seconds)
   - Game type (Regular or Speed mode)

3. **Ready Up**
   - All players mark themselves as ready
   - Host starts the game

4. **Play the Quiz**
   - Listen to music clips from Bollywood movies
   - Type your guess for the movie title
   - Get autocomplete suggestions as you type
   - Score points for correct answers

5. **Scoring**
   - **Regular Mode**: 10 points per correct answer
   - **Speed Mode**: 5-20 points based on how fast you guess

6. **Winner Announced**
   - After all rounds, the player with the highest score wins!

## 🛠️ Tech Stack

### Backend
- **FastAPI**: Modern, fast web framework
- **WebSockets**: Real-time bidirectional communication
- **SQLite**: Lightweight database with 500+ movies
- **Pydantic**: Data validation and settings management
- **httpx**: Async HTTP client for JioSaavn API

### Frontend
- **Vanilla JavaScript**: No framework dependencies
- **WebSocket API**: Real-time updates
- **Modern CSS**: Responsive design with gradients

### External APIs
- **JioSaavn API**: Music streaming and album art

## 📚 Documentation

- **[QUICK_START_REFACTORED.md](QUICK_START_REFACTORED.md)** - Quick start guide for the refactored application
- **[REFACTORING_GUIDE.md](REFACTORING_GUIDE.md)** - Detailed refactoring process documentation
- **[BACKEND_REFACTORING_COMPLETE.md](BACKEND_REFACTORING_COMPLETE.md)** - Complete summary of backend refactoring
- **[BEFORE_AFTER_COMPARISON.md](BEFORE_AFTER_COMPARISON.md)** - Before/after comparison showing improvements
- **[SECURITY.md](SECURITY.md)** - Security features and best practices
- **[CHANGELOG_SECURITY.md](CHANGELOG_SECURITY.md)** - Security-related changes
- **[RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)** - Deployment guide for Render

## 🧪 Testing

### Check Health
```bash
curl http://localhost:8000/health
```

### Create a Room
```bash
curl -X POST http://localhost:8000/api/rooms \
  -H "Content-Type: application/json" \
  -d '{"host_name": "Test User"}'
```

### List Public Rooms
```bash
curl http://localhost:8000/api/rooms
```

## 🌐 Deployment

### Render (Recommended)

1. Connect your GitHub repository to Render
2. Set environment variables:
   - `SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
3. Deploy! The app will automatically:
   - Install dependencies from `requirements.txt`
   - Initialize the database
   - Start the server

See [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) for detailed deployment instructions.

## 🤝 Contributing

Contributions are welcome! The codebase is now modular and easy to extend:

1. **Add a new API endpoint**: Edit `app/routes/api.py`
2. **Add WebSocket action**: Edit `app/routes/websocket.py`
3. **Add a service**: Create a new file in `app/services/`
4. **Update game logic**: Edit `app/services/game_logic.py`

## 📝 License

MIT License - Feel free to use this project for learning or building your own quiz games!

## 🙏 Acknowledgments

- **JioSaavn** for the music API
- **FastAPI** for the excellent web framework
- **GitHub Copilot** for development assistance

---

**Status**: Backend Refactoring Complete ✅ | Frontend Refactoring Pending ⏳  
**Version**: 2.0.0  
**Last Updated**: October 3, 2025
