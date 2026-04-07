"""
Unit tests for Memory Match Arena game logic.

Run with: python3 -m pytest src/test_game_logic.py -v
Or: python3 -m unittest src.test_game_logic -v
"""

import unittest
from src.game_logic import MemoryGame, Difficulty, CardState


class TestGameInitialization(unittest.TestCase):
    """Test game initialization and setup."""

    def test_easy_difficulty_initialization(self):
        """Test that EASY difficulty creates 4x4 grid (8 pairs)."""
        game = MemoryGame(difficulty="EASY")
        self.assertEqual(len(game.cards), 16)
        self.assertEqual(game.total_pairs, 8)
        self.assertEqual(game.difficulty, Difficulty.EASY)

    def test_medium_difficulty_initialization(self):
        """Test that MEDIUM difficulty creates 6x4 grid (12 pairs)."""
        game = MemoryGame(difficulty="MEDIUM")
        self.assertEqual(len(game.cards), 24)
        self.assertEqual(game.total_pairs, 12)

    def test_hard_difficulty_initialization(self):
        """Test that HARD difficulty creates 8x4 grid (16 pairs)."""
        game = MemoryGame(difficulty="HARD")
        self.assertEqual(len(game.cards), 32)
        self.assertEqual(game.total_pairs, 16)

    def test_invalid_difficulty(self):
        """Test that invalid difficulty raises ValueError."""
        with self.assertRaises(ValueError):
            MemoryGame(difficulty="IMPOSSIBLE")

    def test_cards_not_matched_initially(self):
        """Test that all cards start unmatched."""
        game = MemoryGame()
        for card in game.cards:
            self.assertFalse(card.is_matched)

    def test_cards_not_flipped_initially(self):
        """Test that all cards start unflipped."""
        game = MemoryGame()
        for card in game.cards:
            self.assertFalse(card.is_flipped)

    def test_game_state_initialized_correctly(self):
        """Test that game state is initialized with correct values."""
        game = MemoryGame()
        self.assertEqual(game.flipped_indices, [])
        self.assertEqual(game.matched_pairs, 0)
        self.assertEqual(game.moves, 0)
        self.assertFalse(game.is_complete)

    def test_deck_has_pairs(self):
        """Test that deck contains matching pairs."""
        game = MemoryGame(difficulty="EASY")
        symbols = [card.symbol for card in game.cards]
        # Each symbol should appear exactly twice
        for symbol in set(symbols):
            self.assertEqual(symbols.count(symbol), 2)

    def test_game_id_generation(self):
        """Test that each game gets a unique ID."""
        game1 = MemoryGame()
        game2 = MemoryGame()
        self.assertNotEqual(game1.game_id, game2.game_id)

    def test_custom_game_id(self):
        """Test that custom game ID is respected."""
        game = MemoryGame(game_id="test-game-123")
        self.assertEqual(game.game_id, "test-game-123")


class TestCardFlipping(unittest.TestCase):
    """Test card flipping mechanics."""

    def setUp(self):
        """Create a fresh game for each test."""
        self.game = MemoryGame(difficulty="EASY")

    def test_flip_valid_card(self):
        """Test flipping a valid card."""
        response = self.game.flip_card(0)
        self.assertEqual(response["status"], "flipped")
        self.assertEqual(response["flipped_card_index"], 0)
        self.assertTrue(self.game.cards[0].is_flipped)

    def test_flip_card_out_of_bounds_negative(self):
        """Test flipping a card with negative index."""
        with self.assertRaises(ValueError):
            self.game.flip_card(-1)

    def test_flip_card_out_of_bounds_too_high(self):
        """Test flipping a card with index beyond deck size."""
        with self.assertRaises(ValueError):
            self.game.flip_card(100)

    def test_flip_same_card_twice(self):
        """Test that flipping the same card twice raises error."""
        self.game.flip_card(0)
        with self.assertRaises(ValueError):
            self.game.flip_card(0)

    def test_flip_more_than_two_cards(self):
        """Test that flipping more than 2 cards raises error."""
        self.game.flip_card(0)
        self.game.flip_card(1)
        with self.assertRaises(RuntimeError):
            self.game.flip_card(2)

    def test_flip_response_includes_symbol(self):
        """Test that flip response includes the card's symbol."""
        response = self.game.flip_card(0)
        self.assertIn("flipped_card_symbol", response)
        self.assertIsNotNone(response["flipped_card_symbol"])

    def test_flipped_indices_tracked(self):
        """Test that flipped card indices are tracked."""
        self.game.flip_card(0)
        self.game.flip_card(1)
        self.assertEqual(self.game.flipped_indices, [0, 1])


class TestMatchDetection(unittest.TestCase):
    """Test match detection logic."""

    def setUp(self):
        """Create a game and manually set up matching cards."""
        self.game = MemoryGame(difficulty="EASY")

    def test_matching_pair_detection(self):
        """Test that matching pairs are correctly detected."""
        # Find two cards with matching symbols
        target_symbol = self.game.cards[0].symbol
        match_index = next(
            i for i in range(1, len(self.game.cards))
            if self.game.cards[i].symbol == target_symbol
        )

        self.game.flip_card(0)
        flip_response = self.game.flip_card(match_index)
        # check_match is called automatically when 2 cards are flipped
        
        self.assertTrue(flip_response["match_result"]["is_match"])
        self.assertTrue(self.game.cards[0].is_matched)
        self.assertTrue(self.game.cards[match_index].is_matched)

    def test_non_matching_pair_detection(self):
        """Test that non-matching pairs are correctly identified."""
        # Find two cards with different symbols
        symbol1 = self.game.cards[0].symbol
        different_index = next(
            i for i in range(1, len(self.game.cards))
            if self.game.cards[i].symbol != symbol1
        )

        self.game.flip_card(0)
        flip_response = self.game.flip_card(different_index)
        
        self.assertFalse(flip_response["match_result"]["is_match"])
        self.assertFalse(self.game.cards[0].is_matched)
        self.assertFalse(self.game.cards[different_index].is_matched)

    def test_matched_pair_stays_flipped(self):
        """Test that matched pairs remain flipped."""
        target_symbol = self.game.cards[0].symbol
        match_index = next(
            i for i in range(1, len(self.game.cards))
            if self.game.cards[i].symbol == target_symbol
        )

        self.game.flip_card(0)
        self.game.flip_card(match_index)
        # Matched cards are already revealed and remain flipped

        self.assertTrue(self.game.cards[0].is_flipped)
        self.assertTrue(self.game.cards[match_index].is_flipped)

    def test_moves_incremented_on_match(self):
        """Test that moves are incremented when checking a match."""
        target_symbol = self.game.cards[0].symbol
        match_index = next(
            i for i in range(1, len(self.game.cards))
            if self.game.cards[i].symbol == target_symbol
        )

        self.assertEqual(self.game.moves, 0)
        self.game.flip_card(0)
        # flip_card automatically calls check_match when 2 cards are flipped
        self.game.flip_card(match_index)
        self.assertEqual(self.game.moves, 1)

    def test_matched_pairs_count_incremented(self):
        """Test that matched pairs counter is incremented."""
        target_symbol = self.game.cards[0].symbol
        match_index = next(
            i for i in range(1, len(self.game.cards))
            if self.game.cards[i].symbol == target_symbol
        )

        self.assertEqual(self.game.matched_pairs, 0)
        self.game.flip_card(0)
        flip_response = self.game.flip_card(match_index)
        # check_match is called automatically when 2 cards are flipped
        self.assertTrue(flip_response["match_result"]["is_match"])
        self.assertEqual(self.game.matched_pairs, 1)

    def test_can_flip_after_match(self):
        """Test that the game allows flipping new cards after a matched pair."""
        target_symbol = self.game.cards[0].symbol
        match_index = next(
            i for i in range(1, len(self.game.cards))
            if self.game.cards[i].symbol == target_symbol
        )

        self.game.flip_card(0)
        self.game.flip_card(match_index)

        # After a match, the flipped indices should reset and allow a new flip
        self.assertEqual(self.game.flipped_indices, [])
        self.assertFalse(self.game.cards[2].is_flipped)

        response = self.game.flip_card(2)
        self.assertEqual(response["status"], "flipped")
        self.assertEqual(self.game.flipped_indices, [2])


class TestResettingMatches(unittest.TestCase):
    """Test resetting non-matched cards."""

    def setUp(self):
        """Create a fresh game for each test."""
        self.game = MemoryGame(difficulty="EASY")

    def test_non_matched_cards_reset_to_unflipped(self):
        """Test that non-matching cards flip back over."""
        # Find two cards with different symbols
        symbol1 = self.game.cards[0].symbol
        different_index = next(
            i for i in range(1, len(self.game.cards))
            if self.game.cards[i].symbol != symbol1
        )

        self.game.flip_card(0)
        self.game.flip_card(different_index)
        self.game.check_match()
        self.game.reset_match()

        self.assertFalse(self.game.cards[0].is_flipped)
        self.assertFalse(self.game.cards[different_index].is_flipped)

    def test_flipped_indices_cleared_after_reset(self):
        """Test that flipped_indices list is cleared after reset."""
        symbol1 = self.game.cards[0].symbol
        different_index = next(
            i for i in range(1, len(self.game.cards))
            if self.game.cards[i].symbol != symbol1
        )

        self.game.flip_card(0)
        self.game.flip_card(different_index)
        self.game.check_match()
        self.game.reset_match()

        self.assertEqual(self.game.flipped_indices, [])


class TestScoringSystem(unittest.TestCase):
    """Test game scoring."""

    def setUp(self):
        """Create a fresh game for each test."""
        self.game = MemoryGame(difficulty="EASY")

    def test_score_calculation_zero_pairs(self):
        """Test that score is 0 with 0 matched pairs."""
        score = self.game._calculate_score()
        self.assertEqual(score, 0)

    def test_score_calculation_with_pairs(self):
        """Test score calculation: (pairs × 100) - (moves × 5)."""
        # Manually set matched pairs and moves
        self.game.matched_pairs = 5
        self.game.moves = 10
        score = self.game._calculate_score()
        # (5 × 100) - (10 × 5) = 500 - 50 = 450
        self.assertEqual(score, 450)

    def test_score_minimum_zero(self):
        """Test that score never goes below 0."""
        self.game.matched_pairs = 1
        self.game.moves = 100
        score = self.game._calculate_score()
        self.assertGreaterEqual(score, 0)

    def test_perfect_game_score(self):
        """Test score for a perfect game (8 pairs in 8 moves)."""
        self.game.matched_pairs = 8
        self.game.moves = 8
        score = self.game._calculate_score()
        # (8 × 100) - (8 × 5) = 800 - 40 = 760
        self.assertEqual(score, 760)


class TestGameCompletion(unittest.TestCase):
    """Test game completion conditions."""

    def test_game_not_complete_initially(self):
        """Test that game starts incomplete."""
        game = MemoryGame(difficulty="EASY")
        self.assertFalse(game.is_game_complete())

    def test_game_complete_when_all_pairs_matched(self):
        """Test that game is marked complete when all pairs matched."""
        game = MemoryGame(difficulty="EASY")
        
        # Find and match all pairs
        matched_symbols = set()
        for i in range(len(game.cards)):
            card = game.cards[i]
            if card.symbol not in matched_symbols:
                # Find matching card
                match_index = next(
                    j for j in range(i + 1, len(game.cards))
                    if game.cards[j].symbol == card.symbol
                )
                # Flip both cards; flip_card automatically checks for a match
                game.flip_card(i)
                game.flip_card(match_index)
                # Flipped indices are cleared automatically for matched pairs
                matched_symbols.add(card.symbol)
        
        self.assertTrue(game.is_game_complete())

    def test_game_completion_varies_by_difficulty(self):
        """Test that completion requirements differ by difficulty."""
        for difficulty_name in ["EASY", "MEDIUM", "HARD"]:
            game = MemoryGame(difficulty=difficulty_name)
            
            # Find and match all pairs in this game
            matched_symbols = set()
            for i in range(len(game.cards)):
                card = game.cards[i]
                if card.symbol not in matched_symbols:
                    match_index = next(
                        j for j in range(i + 1, len(game.cards))
                        if game.cards[j].symbol == card.symbol
                    )
                    game.flip_card(i)
                    game.flip_card(match_index)
                    matched_symbols.add(card.symbol)
            
            self.assertTrue(game.is_game_complete())


class TestGameState(unittest.TestCase):
    """Test game state serialization."""

    def test_get_game_state_returns_all_fields(self):
        """Test that get_game_state returns complete state."""
        game = MemoryGame(difficulty="EASY")
        state = game.get_game_state()
        
        self.assertEqual(state.game_id, game.game_id)
        self.assertEqual(state.difficulty, "EASY")
        self.assertEqual(len(state.cards), 16)
        self.assertEqual(state.total_pairs, 8)
        self.assertEqual(state.matched_pairs, 0)

    def test_get_game_state_to_dict(self):
        """Test that game state can be serialized to dict."""
        game = MemoryGame()
        state = game.get_game_state()
        state_dict = state.to_dict()
        
        self.assertIsInstance(state_dict, dict)
        self.assertIn("game_id", state_dict)
        self.assertIn("cards", state_dict)
        self.assertIn("score", state_dict)

    def test_public_state_hides_unflipped_cards(self):
        """Test that public state masks hidden card symbols."""
        game = MemoryGame()
        public_state = game.get_public_state()
        
        # All cards should show as hidden (❓) since none are flipped
        for card in public_state["cards"]:
            if not card["is_matched"]:
                self.assertEqual(card["symbol"], "❓")

    def test_public_state_reveals_flipped_cards(self):
        """Test that public state reveals flipped card symbols."""
        game = MemoryGame()
        game.cards[0].is_flipped = True
        
        public_state = game.get_public_state()
        
        # Flipped card should show its symbol
        self.assertNotEqual(public_state["cards"][0]["symbol"], "❓")

    def test_final_stats_on_completion(self):
        """Test final stats calculation on game completion."""
        game = MemoryGame(difficulty="EASY")
        
        # Match all pairs
        matched_symbols = set()
        for i in range(len(game.cards)):
            card = game.cards[i]
            if card.symbol not in matched_symbols:
                # Find matching card
                match_index = next(
                    j for j in range(i + 1, len(game.cards))
                    if game.cards[j].symbol == card.symbol
                )
                game.flip_card(i)
                # flip_card on the second card automatically calls check_match
                game.flip_card(match_index)
                # Matched cards stay marked and flipped; indices reset automatically
                matched_symbols.add(card.symbol)
        
        stats = game.get_final_stats()
        
        self.assertEqual(stats["difficulty"], "EASY")
        self.assertEqual(stats["total_pairs"], 8)
        self.assertEqual(stats["matched_pairs"], 8)
        self.assertEqual(stats["moves"], 8)
        self.assertTrue(stats["completed"])
        self.assertGreater(stats["score"], 0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def test_flip_already_matched_card_raises_error(self):
        """Test that flipping an already matched card raises error."""
        game = MemoryGame(difficulty="EASY")
        
        # Mark a card as matched
        game.cards[0].is_matched = True
        
        with self.assertRaises(ValueError):
            game.flip_card(0)

    def test_check_match_without_two_flipped_raises_error(self):
        """Test that check_match requires exactly 2 flipped cards."""
        game = MemoryGame()
        
        with self.assertRaises(RuntimeError):
            game.check_match()

    def test_reset_match_without_two_flipped_raises_error(self):
        """Test that reset_match requires exactly 2 flipped cards."""
        game = MemoryGame()
        
        with self.assertRaises(RuntimeError):
            game.reset_match()

    def test_deck_shuffle_varies(self):
        """Test that deck shuffling produces different orders (probabilistically)."""
        games = [MemoryGame(difficulty="EASY") for _ in range(5)]
        deck_orders = [
            tuple(card.symbol for card in game.cards) for game in games
        ]
        
        # At least some decks should be different (extremely unlikely to all match)
        unique_orders = set(deck_orders)
        self.assertGreater(len(unique_orders), 1)


if __name__ == "__main__":
    unittest.main()
