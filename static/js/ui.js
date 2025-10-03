/**
 * UI Module
 * Handles UI rendering and updates
 */

import { appState } from './state.js';
import { escapeHtml, getPlayerInitials } from './utils.js';

/**
 * Show a specific view
 * @param {string} viewId - ID of the view to show
 */
export function showView(viewId) {
    appState.dom.views.forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(viewId).classList.add('active');
}

/**
 * Add a game notification to the notifications panel
 * @param {string} message - Notification message
 * @param {string} type - Notification type
 */
export function addGameNotification(message, type = 'info') {
    const notificationDiv = document.createElement('div');
    let className = 'notification-item ';
    
    switch(type) {
        case 'round_start':
            className += 'round-start';
            break;
        case 'correct_guesses':
            className += 'correct';
            break;
        case 'wrong_guesses':
            className += 'wrong';
            break;
        default:
            className += 'round-start';
    }
    
    notificationDiv.className = className;
    notificationDiv.textContent = message;
    appState.dom.notificationsList.appendChild(notificationDiv);
    appState.dom.notificationsList.scrollTop = appState.dom.notificationsList.scrollHeight;
    
    // Keep only last 20 notifications
    while (appState.dom.notificationsList.children.length > 20) {
        appState.dom.notificationsList.removeChild(appState.dom.notificationsList.firstChild);
    }
}

/**
 * Highlight a player on the scoreboard (when they guess correctly)
 * @param {string} playerName - Name of the player to highlight
 */
export function highlightCorrectPlayer(playerName) {
    const scoreItems = document.querySelectorAll('.score-item');
    scoreItems.forEach(item => {
        const nameElement = item.querySelector('.player-name');
        if (nameElement && nameElement.textContent.includes(playerName)) {
            item.classList.add('highlight-correct');
            setTimeout(() => {
                item.classList.remove('highlight-correct');
            }, 2000);
        }
    });
}

/**
 * Add a chat message to the chat box
 * @param {string} playerName - Sender name
 * @param {string} text - Message text
 * @param {boolean} isOwn - Whether this is the current user's message
 */
export function addChatMessage(playerName, text, isOwn = false) {
    const messageDiv = document.createElement('div');
    const isSystem = playerName === 'System';
    
    if (!isSystem) {
        messageDiv.className = `message player ${isOwn ? 'own' : ''}`;
        messageDiv.innerHTML = `
            <div class="message-sender">
                <div class="player-avatar" style="width: 20px; height: 20px; font-size: 0.6rem; margin-right: 6px; display: inline-flex;">
                    ${escapeHtml(getPlayerInitials(playerName))}
                </div>
                ${escapeHtml(playerName)}
            </div>
            <div>${escapeHtml(text)}</div>
        `;
        
        appState.dom.chatBox.appendChild(messageDiv);
        appState.dom.chatBox.scrollTop = appState.dom.chatBox.scrollHeight;
    }
}

/**
 * Show or hide movie suggestions
 * @param {string[]} suggestions - Array of movie suggestions
 */
export function showSuggestions(suggestions) {
    appState.dom.suggestionsDiv.innerHTML = '';
    if (suggestions.length > 0 && !appState.hasSubmittedGuess) {
        suggestions.forEach(suggestion => {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.innerHTML = `<i class="fas fa-film" style="margin-right: 8px; color: var(--primary-color);"></i>${escapeHtml(suggestion)}`;
            div.onclick = () => {
                if (!appState.hasSubmittedGuess) {
                    appState.dom.guessInput.value = suggestion;
                    appState.latestGuess = suggestion;
                    hideSuggestions();
                }
            };
            appState.dom.suggestionsDiv.appendChild(div);
        });
        appState.dom.suggestionsDiv.style.display = 'block';
    } else {
        hideSuggestions();
    }
}

/**
 * Hide movie suggestions
 */
export function hideSuggestions() {
    appState.dom.suggestionsDiv.style.display = 'none';
}

/**
 * Show game settings modal
 */
export function showSettingsModal() {
    appState.dom.totalRoundsInput.value = appState.gameSettings.total_rounds;
    appState.dom.musicDurationInput.value = appState.gameSettings.music_duration;
    
    document.querySelectorAll('.game-type-option').forEach(option => {
        option.classList.remove('selected');
        if (option.dataset.type === appState.gameSettings.game_type) {
            option.classList.add('selected');
        }
    });
    
    appState.dom.settingsModal.classList.add('active');
}

/**
 * Close game settings modal
 */
export function closeSettingsModal() {
    appState.dom.settingsModal.classList.remove('active');
}
