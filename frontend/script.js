class ChatApp {
    constructor() {
        this.messagesContainer = document.getElementById('messagesContainer');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.loadingIndicator = document.getElementById('loadingIndicator');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.selectedNeighborhood = null;
        this.isProcessing = false;
        this.messageHistory = [];
        
        this.initializeEventListeners();
        this.autoResizeTextarea();
    }

    initializeEventListeners() {
        // Send message on Enter (but allow Shift+Enter for new lines)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.autoResizeTextarea();
        });

        // Focus input on page load
        window.addEventListener('load', () => {
            this.messageInput.focus();
        });
    }

    setNeighborhood(name) {
        this.selectedNeighborhood = name;
    }

    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        
        if (!message || this.isProcessing) {
            return;
        }

        // Clear input and reset height
        this.messageInput.value = '';
        this.messageInput.style.height = '50px';

        // Add user message to chat
        this.addMessage(message, 'user');

        // Show typing indicator
        this.showTypingIndicator();

        // Disable input and button
        this.setProcessingState(true);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    message: message, 
                    neighborhood: this.selectedNeighborhood 
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.error) {
                this.addErrorMessage(data.error);
            } else {
                // Hide typing indicator
                this.hideTypingIndicator();
                
                // Add assistant response(s)
                if (data.messages && data.messages.length > 0) {
                    data.messages.forEach(msg => {
                        if (msg && msg.trim()) {
                            this.addMessage(msg, 'assistant');
                        }
                    });
                } else {
                    this.addMessage('I apologize, but I couldn\'t generate a response. Please try again.', 'assistant');
                }
            }

        } catch (error) {
            console.error('Error:', error);
            this.hideTypingIndicator();
            this.addErrorMessage('Sorry, I encountered an error while processing your request. Please check your connection and try again.');
        } finally {
            // Re-enable input and button
            this.setProcessingState(false);
        }
    }

    addMessage(content, sender) {
        // Remove empty state if it exists
        const emptyState = this.messagesContainer.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        messageDiv.innerHTML = `
            <div class="message-avatar ${sender}">${sender === 'user' ? 'You' : 'AI'}</div>
            <div class="message-content">
                ${this.formatMessage(content)}
                <div class="message-time">${timestamp}</div>
            </div>
        `;

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
        
        // Store in history
        this.messageHistory.push({ content, sender, timestamp });
    }

    addErrorMessage(error) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = `
            <strong>⚠️ Error:</strong> ${error}
        `;
        
        this.messagesContainer.appendChild(errorDiv);
        this.scrollToBottom();
    }

    formatMessage(content) {
        // Convert URLs to clickable links
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        content = content.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
        
        // Convert line breaks to <br> tags
        content = content.replace(/\n/g, '<br>');
        
        // Highlight code blocks (simple implementation)
        content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        return content;
    }

    showTypingIndicator() {
        this.typingIndicator.style.display = 'flex';
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.typingIndicator.style.display = 'none';
    }

    setProcessingState(processing) {
        this.isProcessing = processing;
        this.sendButton.disabled = processing;
        this.messageInput.disabled = processing;
        this.loadingIndicator.style.display = processing ? 'flex' : 'none';
        
        if (processing) {
            this.sendButton.innerHTML = '⏳';
        } else {
            this.sendButton.innerHTML = '➤';
        }
    }

    scrollToBottom() {
        setTimeout(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }, 100);
    }

    // Method to clear chat history
    clearChat() {
        this.messagesContainer.innerHTML = `
            <div class="empty-state">
                <h3>👋 Welcome!</h3>
                <p>I can help you analyze NYC housing market data, compare rent vs buy scenarios, calculate mortgage payments, and generate charts. Try asking me something like:</p>
                <p style="margin-top: 15px; font-style: italic;">
                    "What's the median rent in Brooklyn in 2023?"<br>
                    "Compare home prices in Manhattan vs Queens"<br>
                    "Calculate monthly mortgage for a $500k home with 20% down"
                </p>
            </div>
        `;
        this.messageHistory = [];
    }
}

// Initialize the chat app when the page loads
let chatApp;

document.addEventListener('DOMContentLoaded', () => {
    chatApp = new ChatApp();
});

// Global function for the onclick handler
function sendMessage() {
    if (chatApp) {
        chatApp.sendMessage();
    }
}

// Global function for clearing chat
function clearChat() {
    if (chatApp) {
        chatApp.clearChat();
    }
}

// Add some CSS for code blocks
const style = document.createElement('style');
style.textContent = `
    code {
        background: #f8f9fa;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
        font-size: 0.9em;
        color: #e83e8c;
    }
    
    .message-content a {
        color: #007bff;
        text-decoration: none;
    }
    
    .message-content a:hover {
        text-decoration: underline;
    }
    
    .message.user .message-content a {
        color: #fff;
        text-decoration: underline;
    }
`;
document.head.appendChild(style); 