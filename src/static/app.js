/**
 * Memory Match Arena - Client-side Game Logic
 * Handles game initialization, card flipping, UI updates, and state management
 */

// Global game state
let currentGame = {
    gameId: null,
    difficulty: 'MEDIUM',
    playerEmail: '',
    playerName: '',
    gameState: {},
    isFlipping: false,
    previousScreen: 'setupScreen'
};

// ============= Screen Navigation =============

function showScreen(screenId) {
    // Hide all screens
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    
    // Show target screen
    document.getElementById(screenId).classList.add('active');
}

// ============= Game Setup =============

document.getElementById('startGameBtn').addEventListener('click', startNewGame);
document.getElementById('leaderboardBtn').addEventListener('click', showLeaderboard);
document.getElementById('quitGameBtn').addEventListener('click', quitGame);
document.getElementById('playAgainBtn').addEventListener('click', resetToSetup);
document.getElementById('leaderboardFromWinBtn').addEventListener('click', showLeaderboard);
document.getElementById('backFromLeaderboardBtn').addEventListener('click', backToSetup);

async function startNewGame() {
    const nameInput = document.getElementById('playerName');
    const emailInput = document.getElementById('playerEmail');
    const difficultySelect = document.getElementById('difficultySelect');

    const playerName = nameInput.value.trim() || 'Guest';
    const playerEmail = emailInput.value.trim();
    
    if (!playerEmail) {
        alert('Please enter your email address');
        emailInput.focus();
        return;
    }

    // Validate email format
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(playerEmail)) {
        alert('Please enter a valid email address');
        emailInput.focus();
        return;
    }

    currentGame.playerName = playerName;
    currentGame.playerEmail = playerEmail;
    currentGame.difficulty = difficultySelect.value;

    try {
        const response = await fetch('/game/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                difficulty: currentGame.difficulty,
                player_email: playerEmail,
                player_name: playerName
            })
        });

        if (!response.ok) {
            throw new Error('Failed to start game');
        }

        const data = await response.json();
        currentGame.gameId = data.game_id;
        currentGame.gameState = data.game_state;

        renderGameBoard();
        updateGameStats();
        showScreen('gameScreen');
    } catch (error) {
        alert('Error starting game: ' + error.message);
        console.error('Error:', error);
    }
}

// ============= Game Board Rendering =============

function renderGameBoard() {
    const gameBoard = document.getElementById('gameBoard');
    gameBoard.innerHTML = '';
    
    const cards = currentGame.gameState.cards;
    const gridSize = calculateGridSize(cards.length);
    
    gameBoard.style.gridTemplateColumns = `repeat(${gridSize.cols}, 1fr)`;
    gameBoard.style.gridTemplateRows = `repeat(${gridSize.rows}, 1fr)`;
    
    cards.forEach((card, index) => {
        const cardElement = document.createElement('div');
        cardElement.className = 'card';
        cardElement.dataset.index = index;
        
        // Add classes for state
        if (card.is_flipped) cardElement.classList.add('flipped');
        if (card.is_matched) cardElement.classList.add('matched');
        
        // Set the card content
        const cardContent = document.createElement('div');
        cardContent.className = 'card-content';
        cardContent.innerHTML = `
            <div class="card-front">?</div>
            <div class="card-back">${card.symbol}</div>
        `;
        
        cardElement.appendChild(cardContent);
        cardElement.addEventListener('click', () => flipCard(index));
        
        gameBoard.appendChild(cardElement);
    });
}

function calculateGridSize(totalCards) {
    if (totalCards === 16) return { rows: 4, cols: 4 };    // EASY: 4x4
    if (totalCards === 24) return { rows: 4, cols: 6 };    // MEDIUM: 6x4
    if (totalCards === 32) return { rows: 4, cols: 8 };    // HARD: 8x4
    return { rows: 4, cols: 4 };
}

// ============= Card Flipping =============

async function flipCard(cardIndex) {
    // Prevent flipping during animation or if card is already matched
    if (currentGame.isFlipping) return;
    
    const card = currentGame.gameState.cards[cardIndex];
    if (card.is_matched || card.is_flipped) return;

    currentGame.isFlipping = true;

    try {
        const response = await fetch(`/game/${currentGame.gameId}/move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ card_index: cardIndex })
        });

        if (!response.ok) {
            throw new Error('Failed to flip card');
        }

        const data = await response.json();
        currentGame.gameState = data.game_state;
        
        renderGameBoard();
        updateGameStats();

        // If 2 cards were just flipped, check if they match
        if (data.move_result.cards_flipped === 2) {
            const moveResult = data.move_result.match_result;
            
            if (moveResult.is_match) {
                // Cards match - keep them flipped
                showMessage('✅ Match found!', 'success', 800);
            } else {
                // Cards don't match - flip them back after delay
                showMessage('❌ No match, try again!', 'error', 800);
                await new Promise(resolve => setTimeout(resolve, 1500));
                
                // Reset the non-matching cards
                await resetCards();
            }
        }

        // Check if game is complete
        if (currentGame.gameState.is_complete) {
            await new Promise(resolve => setTimeout(resolve, 500));
            finishGame();
        }

    } catch (error) {
        console.error('Error flipping card:', error);
        showMessage('Error: Could not flip card', 'error');
    } finally {
        currentGame.isFlipping = false;
    }
}

async function resetCards() {
    try {
        const response = await fetch(`/game/${currentGame.gameId}/reset`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            throw new Error('Failed to reset cards');
        }

        const data = await response.json();
        currentGame.gameState = data.game_state;
        renderGameBoard();
        updateGameStats();

    } catch (error) {
        console.error('Error resetting cards:', error);
    }
}

// ============= Game Statistics & UI Updates =============

function updateGameStats() {
    document.getElementById('score').innerText = currentGame.gameState.score;
    document.getElementById('moves').innerText = currentGame.gameState.moves;
    
    const pairInfo = `${currentGame.gameState.matched_pairs}/${currentGame.gameState.total_pairs}`;
    document.getElementById('pairs').innerText = pairInfo;
}

function showMessage(text, type = 'info', duration = 2000) {
    const messageDiv = document.getElementById('gameMessage');
    messageDiv.textContent = text;
    messageDiv.className = `game-message ${type}`;
    messageDiv.style.display = 'block';
    
    if (duration > 0) {
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, duration);
    }
}

// ============= Game Completion =============

async function finishGame() {
    try {
        const response = await fetch(`/game/${currentGame.gameId}/finish`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                player_email: currentGame.playerEmail,
                player_name: currentGame.playerName
            })
        });

        if (!response.ok) {
            throw new Error('Failed to finish game');
        }

        const data = await response.json();
        const finalStats = data.final_stats;

        // Update win screen
        document.getElementById('finalScore').innerText = finalStats.score;
        document.getElementById('finalMoves').innerText = finalStats.moves;
        document.getElementById('finalDifficulty').innerText = finalStats.difficulty;

        showScreen('winScreen');

    } catch (error) {
        alert('Error saving game: ' + error.message);
        console.error('Error:', error);
    }
}

// ============= Navigation =============

function quitGame() {
    if (confirm('Are you sure you want to quit? Your progress will be lost.')) {
        currentGame.gameId = null;
        resetToSetup();
    }
}

function resetToSetup() {
    showScreen('setupScreen');
}

function backToSetup() {
    showScreen('setupScreen');
}

// ============= Leaderboard =============

async function showLeaderboard() {
    currentGame.previousScreen = document.querySelector('.screen.active').id;
    
    try {
        const response = await fetch('/leaderboard');
        
        if (!response.ok) {
            throw new Error('Failed to load leaderboard');
        }

        const data = await response.json();
        const leaderboard = data.leaderboard;

        const tbody = document.getElementById('leaderboardBody');
        tbody.innerHTML = '';

        if (leaderboard.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px;">No scores yet. Be first!</td></tr>';
        } else {
            leaderboard.forEach(player => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${player.rank}</td>
                    <td>${player.name}</td>
                    <td>${player.high_score}</td>
                    <td>${player.games_played}</td>
                `;
                tbody.appendChild(row);
            });
        }

        showScreen('leaderboardScreen');

    } catch (error) {
        alert('Error loading leaderboard: ' + error.message);
        console.error('Error:', error);
    }
}

// ============= Initialization =============

document.addEventListener('DOMContentLoaded', () => {
    // Pre-fill email if available (from localStorage for demo)
    const savedEmail = localStorage.getItem('playerEmail');
    const savedName = localStorage.getItem('playerName');
    
    if (savedEmail) {
        document.getElementById('playerEmail').value = savedEmail;
    }
    if (savedName) {
        document.getElementById('playerName').value = savedName;
    }

    // Focus on email input on load
    document.getElementById('playerEmail').focus();
});

// Save player info to localStorage when game starts
document.getElementById('startGameBtn').addEventListener('click', function() {
    const email = document.getElementById('playerEmail').value;
    const name = document.getElementById('playerName').value;
    if (email) localStorage.setItem('playerEmail', email);
    if (name) localStorage.setItem('playerName', name);
});
