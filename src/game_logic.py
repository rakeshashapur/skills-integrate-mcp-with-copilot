"""
Memory Match Arena - Core Game Logic

Pure Python game engine with no UI dependencies.
Reusable across web (FastAPI), CLI, and other platforms.
"""

import random
from enum import Enum
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


class Difficulty(Enum):
    """Game difficulty levels with grid dimensions."""
    EASY = (4, 4)      # 16 cards (8 pairs)
    MEDIUM = (6, 4)    # 24 cards (12 pairs)
    HARD = (8, 4)      # 32 cards (16 pairs)

    def pair_count(self) -> int:
        """Return number of pairs for this difficulty."""
        return (self.value[0] * self.value[1]) // 2


@dataclass
class CardState:
    """Represents the state of a single card."""
    card_id: int
    is_flipped: bool
    is_matched: bool
    symbol: str  # Visual symbol for the card (emoji or character)

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return asdict(self)


@dataclass
class GameState:
    """Represents the complete game state."""
    game_id: str
    difficulty: str
    cards: List[CardState]
    flipped_indices: List[int]
    matched_pairs: int
    total_pairs: int
    moves: int
    is_complete: bool
    score: int
    started_at: str

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return {
            "game_id": self.game_id,
            "difficulty": self.difficulty,
            "cards": [card.to_dict() for card in self.cards],
            "flipped_indices": self.flipped_indices,
            "matched_pairs": self.matched_pairs,
            "total_pairs": self.total_pairs,
            "moves": self.moves,
            "is_complete": self.is_complete,
            "score": self.score,
            "started_at": self.started_at,
        }


class MemoryGame:
    """
    Core Memory/Concentration game engine.
    
    Game Rules:
    - Player flips two cards at a time
    - If cards match, they stay revealed and a point is scored
    - If cards don't match, they flip back over
    - Game is won when all pairs are matched
    
    Scoring:
    - Base score per pair: 100 points
    - Penalty per move: -5 points
    - Final score = (matched_pairs × 100) - (total_moves × 5)
    - Minimum score: 0
    """

    # Card symbols for visual identification
    SYMBOLS = [
        "🌟", "🎨", "🎭", "🎪", "🎬", "🎮", "🎲", "🎯",
        "🌈", "🦋", "🐢", "🦊", "🐸", "🦅", "🦁", "🐻"
    ]

    # Scoring constants
    BASE_POINTS_PER_PAIR = 100
    PENALTY_PER_MOVE = 5

    def __init__(self, difficulty: str = "EASY", game_id: Optional[str] = None):
        """
        Initialize a new Memory Match game.
        
        Args:
            difficulty: One of "EASY", "MEDIUM", "HARD"
            game_id: Unique game identifier (generated if not provided)
        
        Raises:
            ValueError: If difficulty is not recognized
        """
        try:
            self.difficulty = Difficulty[difficulty.upper()]
        except KeyError:
            raise ValueError(f"Invalid difficulty: {difficulty}. Choose from: EASY, MEDIUM, HARD")
        
        self.game_id = game_id or self._generate_game_id()
        self.cards: List[CardState] = []
        self.flipped_indices: List[int] = []
        self.matched_pairs = 0
        self.total_pairs = self.difficulty.pair_count()
        self.moves = 0
        self.is_complete = False
        self.started_at = datetime.now().isoformat()
        
        self._initialize_deck()

    def _generate_game_id(self) -> str:
        """Generate a unique game ID."""
        import uuid
        return str(uuid.uuid4())[:8]

    def _initialize_deck(self) -> None:
        """Create and shuffle the card deck."""
        rows, cols = self.difficulty.value
        total_cards = rows * cols
        
        # Create pairs of symbols
        symbols_needed = total_cards // 2
        selected_symbols = self.SYMBOLS[:symbols_needed]
        
        # Each symbol appears twice (one pair)
        deck = selected_symbols + selected_symbols
        random.shuffle(deck)
        
        # Create card objects
        self.cards = [
            CardState(
                card_id=i,
                is_flipped=False,
                is_matched=False,
                symbol=deck[i]
            )
            for i in range(total_cards)
        ]

    def flip_card(self, card_index: int) -> Dict:
        """
        Flip a card at the given index.
        
        Args:
            card_index: 0-based index of the card to flip
        
        Returns:
            Dict with response status and game state update
        
        Raises:
            ValueError: If index is out of bounds or card is already matched
            RuntimeError: If more than 2 cards are flipped
        """
        # Validation
        if not (0 <= card_index < len(self.cards)):
            raise ValueError(f"Card index {card_index} out of bounds")
        
        if self.cards[card_index].is_matched:
            raise ValueError(f"Card {card_index} is already matched")
        
        if card_index in self.flipped_indices:
            raise ValueError(f"Card {card_index} is already flipped")
        
        if len(self.flipped_indices) >= 2:
            raise RuntimeError("Cannot flip more than 2 cards at a time")
        
        # Flip the card
        self.flipped_indices.append(card_index)
        self.cards[card_index].is_flipped = True
        
        response = {
            "status": "flipped",
            "flipped_card_index": card_index,
            "flipped_card_symbol": self.cards[card_index].symbol,
            "cards_flipped": len(self.flipped_indices),
        }
        
        # If 2 cards are flipped, check for match
        if len(self.flipped_indices) == 2:
            self.moves += 1
            match_result = self.check_match()
            response["match_result"] = match_result
            response["moves"] = self.moves
            response["score"] = self._calculate_score()

            # If the two cards match, clear flipped indices for the next move.
            if match_result["is_match"]:
                self.flipped_indices = []
        
        return response

    def check_match(self) -> Dict:
        """
        Check if the two flipped cards match.
        
        Returns:
            Dict with match result and game state
        
        Raises:
            RuntimeError: If not exactly 2 cards are flipped
        """
        if len(self.flipped_indices) != 2:
            raise RuntimeError("Must have exactly 2 flipped cards to check match")
        
        idx1, idx2 = self.flipped_indices
        card1 = self.cards[idx1]
        card2 = self.cards[idx2]
        
        is_match = card1.symbol == card2.symbol
        
        if is_match:
            # Mark cards as matched
            card1.is_matched = True
            card2.is_matched = True
            self.matched_pairs += 1
            
            # Check if game is complete
            if self.matched_pairs == self.total_pairs:
                self.is_complete = True
        
        return {
            "is_match": is_match,
            "symbols": [card1.symbol, card2.symbol],
            "matched_pairs": self.matched_pairs,
            "total_pairs": self.total_pairs,
            "game_complete": self.is_complete,
        }

    def reset_match(self) -> Dict:
        """
        Reset non-matched flipped cards back to unflipped state.
        
        Only call this after check_match() returns False.
        Matched cards stay revealed.
        
        Returns:
            Dict with reset information
        """
        if len(self.flipped_indices) != 2:
            raise RuntimeError("Must have exactly 2 flipped cards to reset")
        
        idx1, idx2 = self.flipped_indices
        
        # Only reset if they don't match
        if not (self.cards[idx1].is_matched and self.cards[idx2].is_matched):
            self.cards[idx1].is_flipped = False
            self.cards[idx2].is_flipped = False
        
        self.flipped_indices = []
        
        return {
            "status": "reset",
            "cards_revealed": sum(1 for card in self.cards if card.is_matched),
        }

    def _calculate_score(self) -> int:
        """
        Calculate current score based on matches and moves.
        
        Formula: (matched_pairs × 100) - (moves × 5)
        Minimum score clamped to 0.
        """
        score = (self.matched_pairs * self.BASE_POINTS_PER_PAIR) - (
            self.moves * self.PENALTY_PER_MOVE
        )
        return max(0, score)

    def is_game_complete(self) -> bool:
        """Check if all pairs have been matched."""
        return self.is_complete

    def get_game_state(self) -> GameState:
        """
        Get the complete, JSON-serializable game state.
        
        Returns:
            GameState dataclass with all game information
        """
        return GameState(
            game_id=self.game_id,
            difficulty=self.difficulty.name,
            cards=self.cards,
            flipped_indices=self.flipped_indices,
            matched_pairs=self.matched_pairs,
            total_pairs=self.total_pairs,
            moves=self.moves,
            is_complete=self.is_complete,
            score=self._calculate_score(),
            started_at=self.started_at,
        )

    def get_public_state(self) -> Dict:
        """
        Get game state suitable for sending to client (hides unflipped cards).
        
        Returns:
            Dict with safe game state for client-side rendering
        """
        state = self.get_game_state()
        state_dict = state.to_dict()
        
        # Hide symbols of unflipped cards
        public_cards = []
        for card in state_dict["cards"]:
            if not card["is_flipped"] and not card["is_matched"]:
                card["symbol"] = "❓"  # Hidden card indicator
            public_cards.append(card)
        
        state_dict["cards"] = public_cards
        return state_dict

    def get_final_stats(self) -> Dict:
        """
        Get final game statistics (call when game is complete).
        
        Returns:
            Dict with final score, difficulty, moves, and other stats
        """
        return {
            "game_id": self.game_id,
            "difficulty": self.difficulty.name,
            "score": self._calculate_score(),
            "total_pairs": self.total_pairs,
            "matched_pairs": self.matched_pairs,
            "moves": self.moves,
            "efficiency": self.matched_pairs / self.moves if self.moves > 0 else 0,
            "completed": self.is_complete,
            "completed_at": datetime.now().isoformat(),
        }
