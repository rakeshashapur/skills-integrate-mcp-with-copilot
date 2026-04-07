"""
Memory Match Arena - FastAPI Backend

REST API for the Memory Match card flipping game with persistent scoring.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import os
from pathlib import Path
import sqlite3
import json
from datetime import datetime
import uuid

from src.game_logic import MemoryGame

app = FastAPI(
    title="Memory Match Arena API",
    description="REST API for Memory Match game with leaderboard persistence"
)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")

# In-memory game storage (maps game_id to MemoryGame instance)
# In production, this would use Redis or persistent session storage
active_games = {}

# Database setup
DB_FILE = 'memory_game.db'


def init_db():
    """Initialize SQLite database with Players and GameScores tables."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Players table: track high scores and stats
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        high_score INTEGER DEFAULT 0,
        games_played INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )''')

    # GameScores table: track all game results
    c.execute('''CREATE TABLE IF NOT EXISTS game_scores (
        id TEXT PRIMARY KEY,
        player_id TEXT NOT NULL,
        game_id TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        score INTEGER NOT NULL,
        total_pairs INTEGER NOT NULL,
        matched_pairs INTEGER NOT NULL,
        moves INTEGER NOT NULL,
        efficiency REAL NOT NULL,
        completed_at TEXT NOT NULL,
        FOREIGN KEY(player_id) REFERENCES players(id)
    )''')

    conn.commit()
    conn.close()


def get_or_create_player(email: str, name: str = None) -> str:
    """Get or create a player record, return player_id."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Check if player exists
    c.execute('SELECT id FROM players WHERE email = ?', (email,))
    result = c.fetchone()

    if result:
        conn.close()
        return result[0]

    # Create new player
    player_id = str(uuid.uuid4())
    player_name = name or email.split('@')[0]
    now = datetime.now().isoformat()

    c.execute(
        'INSERT INTO players (id, name, email, created_at) VALUES (?, ?, ?, ?)',
        (player_id, player_name, email, now)
    )
    conn.commit()
    conn.close()
    return player_id


def save_game_score(player_id: str, game_stats: dict) -> None:
    """Save final game statistics to database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    score_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    c.execute('''INSERT INTO game_scores 
        (id, player_id, game_id, difficulty, score, total_pairs, matched_pairs, moves, efficiency, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            score_id,
            player_id,
            game_stats["game_id"],
            game_stats["difficulty"],
            game_stats["score"],
            game_stats["total_pairs"],
            game_stats["matched_pairs"],
            game_stats["moves"],
            game_stats["efficiency"],
            now
        )
    )

    # Update player's high score
    c.execute('SELECT high_score FROM players WHERE id = ?', (player_id,))
    current_high = c.fetchone()[0]

    if game_stats["score"] > current_high:
        c.execute('UPDATE players SET high_score = ? WHERE id = ?', (game_stats["score"], player_id))

    # Increment games played
    c.execute('UPDATE players SET games_played = games_played + 1 WHERE id = ?', (player_id,))

    conn.commit()
    conn.close()


def get_leaderboard(limit: int = 10):
    """Get top players by high score."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('''SELECT name, email, high_score, games_played FROM players
        ORDER BY high_score DESC LIMIT ?''', (limit,))

    rows = c.fetchall()
    conn.close()

    return [
        {
            "rank": i + 1,
            "name": row[0],
            "email": row[1],
            "high_score": row[2],
            "games_played": row[3]
        }
        for i, row in enumerate(rows)
    ]


# Initialize database on startup
init_db()


# ============= Pydantic Models =============

class GameMove(BaseModel):
    """Model for card flip request."""
    card_index: int


class StartGameRequest(BaseModel):
    """Model for game start request."""
    difficulty: str = "EASY"  # EASY, MEDIUM, or HARD
    player_email: str
    player_name: str = None


class FinishGameRequest(BaseModel):
    """Model for game finish request."""
    player_email: str
    player_name: str = None


# ============= Routes =============

@app.get("/")
def root():
    """Redirect to game UI."""
    return RedirectResponse(url="/static/index.html")


@app.post("/game/start")
def start_game(request: StartGameRequest):
    """
    Start a new Memory Match game.
    
    Returns:
        - game_id: Unique identifier for this game session
        - difficulty: Game difficulty level
        - cards: Current game state (all cards hidden)
        - Total pairs, current moves, score
    """
    try:
        # Create game instance
        game = MemoryGame(difficulty=request.difficulty)
        active_games[game.game_id] = game

        return {
            "status": "started",
            "game_id": game.game_id,
            "game_state": game.get_public_state()
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/move")
def make_move(game_id: str, move: GameMove):
    """
    Flip a card in the game.
    
    Args:
        game_id: Game session ID
        move: Card index to flip (0-based)
    
    Returns:
        Updated game state and move result
    """
    # Validate game exists
    if game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found or session expired")

    game = active_games[game_id]

    try:
        # Perform the flip
        flip_response = game.flip_card(move.card_index)

        # If 2 cards are flipped and they don't match, need to reset them
        # (The frontend will handle the timing of when to show the reset animation)
        
        return {
            "status": "success",
            "move_result": flip_response,
            "game_state": game.get_public_state()
        }

    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/reset")
def reset_mismatch(game_id: str):
    """
    Reset non-matching flipped cards back to hidden state.
    Call this after the client displays a non-matching pair.
    """
    if game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")

    game = active_games[game_id]

    try:
        reset_response = game.reset_match()
        return {
            "status": "success",
            "reset_result": reset_response,
            "game_state": game.get_public_state()
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/finish")
def finish_game(game_id: str, request: FinishGameRequest):
    """
    Mark game as finished and save score to database.
    
    Args:
        game_id: Game session ID
        request: Player email and name (for leaderboard)
    
    Returns:
        Final game statistics and saved score info
    """
    if game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")

    game = active_games[game_id]

    if not game.is_game_complete():
        raise HTTPException(status_code=400, detail="Game is not complete")

    try:
        # Get player or create new
        player_id = get_or_create_player(request.player_email, request.player_name)

        # Get final stats
        final_stats = game.get_final_stats()

        # Save to database
        save_game_score(player_id, final_stats)

        # Clean up active game
        del active_games[game_id]

        return {
            "status": "completed",
            "final_stats": final_stats,
            "message": f"Game saved! Final score: {final_stats['score']}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving game: {str(e)}")


@app.get("/game/{game_id}")
def get_game_state(game_id: str):
    """Get current game state (public view, hides unflipped cards)."""
    if game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")

    game = active_games[game_id]
    return {
        "status": "active",
        "game_state": game.get_public_state()
    }


@app.get("/leaderboard")
def get_leaderboard_endpoint(limit: int = 10):
    """
    Get top players by high score.
    
    Args:
        limit: Number of top scores to return (default 10, max 100)
    
    Returns:
        List of top players with rank, name, high_score, games_played
    """
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")

    leaderboard = get_leaderboard(limit)
    return {
        "status": "success",
        "leaderboard": leaderboard
    }


@app.get("/player-stats")
def get_player_stats(email: str):
    """
    Get a player's statistics and recent games.
    
    Args:
        email: Player's email address
    
    Returns:
        Player profile with stats and recent game scores
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Get player info
    c.execute('''SELECT id, name, high_score, games_played, created_at FROM players WHERE email = ?''', (email,))
    player_row = c.fetchone()

    if not player_row:
        raise HTTPException(status_code=404, detail="Player not found")

    player_id, name, high_score, games_played, created_at = player_row

    # Get recent games
    c.execute('''SELECT difficulty, score, moves, matched_pairs, total_pairs, completed_at FROM game_scores
        WHERE player_id = ? ORDER BY completed_at DESC LIMIT 5''', (player_id,))

    recent_games = [
        {
            "difficulty": row[0],
            "score": row[1],
            "moves": row[2],
            "matched_pairs": row[3],
            "total_pairs": row[4],
            "completed_at": row[5]
        }
        for row in c.fetchall()
    ]

    conn.close()

    return {
        "status": "success",
        "player": {
            "name": name,
            "email": email,
            "high_score": high_score,
            "games_played": games_played,
            "member_since": created_at
        },
        "recent_games": recent_games
    }


# Health check endpoint
@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "Memory Match Arena API"}
