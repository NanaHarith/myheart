class WebSocketManager {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 1000; // Start with 1 second
        this.heartbeatInterval = null;
        this.isConnected = false;
        this.pendingReconnection = false;
    }

    connect() {
        if (this.socket && this.isConnected) return;
        if (this.pendingReconnection) return;

        this.socket = io({
            reconnection: false // We'll handle reconnection ourselves
        });

        this.setupEventListeners();
        this.startHeartbeat();
    }

    setupEventListeners() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.reconnectInterval = 1000;
            this.pendingReconnection = false;

            // Emit status for UI updates
            document.getElementById('status').textContent = 'Connected';
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.isConnected = false;
            this.handleDisconnect();

            // Emit status for UI updates
            document.getElementById('status').textContent = 'Disconnected - Attempting to reconnect...';
        });

        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.handleDisconnect();
        });

        this.socket.on('pong', () => {
            this.lastPongTime = Date.now();
        });

        // Re-register all the original event handlers
        this.socket.on('connection_established', () => {
            console.log('Connection established with server');
        });

        this.socket.on('speech_detected', (data) => {
            // Re-implement your speech detection handler
            document.getElementById('speechStatus').textContent = data.detected ? 'Speech detected' : 'No speech';
        });

        this.socket.on('ai_response', (data) => {
            const resultDiv = document.getElementById('result');
            resultDiv.textContent = data.text;
        });

        this.socket.on('audio_chunk', (data) => {
            // Implement your audio chunk handler
            if (data.chunk) {
                // Handle audio chunk playback
            }
        });
    }

    startHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }

        this.lastPongTime = Date.now();

        this.heartbeatInterval = setInterval(() => {
            if (!this.isConnected) return;

            // Check if we haven't received a pong in 5 seconds
            if (Date.now() - this.lastPongTime > 5000) {
                console.log('No heartbeat response - reconnecting');
                this.reconnect();
                return;
            }

            this.socket.emit('ping');
        }, 2000); // Send heartbeat every 2 seconds
    }

    handleDisconnect() {
        this.isConnected = false;
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }
        this.reconnect();
    }

    reconnect() {
        if (this.pendingReconnection) return;
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnection attempts reached');
            document.getElementById('status').textContent = 'Connection failed - Please refresh the page';
            return;
        }

        this.pendingReconnection = true;
        this.reconnectAttempts++;

        // Exponential backoff
        const timeout = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 10000);

        console.log(`Attempting to reconnect in ${timeout}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            if (this.socket) {
                this.socket.close();
            }
            this.connect();
        }, timeout);
    }

    // Method to emit events safely
    emit(eventName, data) {
        if (!this.isConnected) {
            console.warn('Attempted to emit while disconnected:', eventName);
            return false;
        }
        this.socket.emit(eventName, data);
        return true;
    }
}

// Export for use in other files
window.WebSocketManager = WebSocketManager;