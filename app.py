# app.py
import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import logging
from datetime import datetime
from conversation_manager import conversation_manager
from streaming_tts import tts_service

# Configuration flags
USE_STREAMING = True
SILENCE_THRESHOLD = 3  # seconds
DEBOUNCE_DELAY = 2  # seconds
last_transcript_time = None

# Load environment variables
load_dotenv()

# Create logs directory
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
log_filename = os.path.join('logs', f"app_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    filename=log_filename,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected to Socket.IO")
    print("Client connected to Socket.IO")
    conversation_manager.start_session()

@socketio.on('user_transcript')
def handle_transcript(data):
    global last_transcript_time
    current_time = datetime.now()

    if last_transcript_time and (current_time - last_transcript_time).total_seconds() < DEBOUNCE_DELAY:
        return

    last_transcript_time = current_time
    try:
        transcript = data.get('text', '')
        logger.info(f"Received transcript: {transcript}")
        print(f"Received transcript: {transcript}")

        # Get AI response
        ai_response = conversation_manager.generate_response(transcript)
        if not ai_response:
            return

        # Get audio response
        if USE_STREAMING:
            audio_data = tts_service.get_stream(ai_response)
            if audio_data:
                logger.info(f"Sending audio response of size: {len(audio_data)} bytes")
                emit('response', {
                    'text': ai_response,
                    'audio': audio_data,
                    'streaming': True
                })
            else:
                logger.error("No audio data received from Speechify")
                emit('response', {'text': ai_response})
        else:
            audio_data = tts_service.get_speech(ai_response)
            if audio_data:
                logger.info(f"Sending audio response of size: {len(audio_data)} bytes")
                emit('response', {
                    'text': ai_response,
                    'audio': audio_data,
                    'streaming': False
                })
            else:
                logger.error("No audio data received from Speechify")
                emit('response', {'text': ai_response})

    except Exception as e:
        logger.error(f"Error handling transcript: {str(e)}")
        print(f"Error handling transcript: {str(e)}")

if __name__ == '__main__':
    host = os.getenv('HOST', 'localhost')
    port = int(os.getenv('PORT', 5000))
    print(f"Flask app running on http://{host}:{port}/")
    socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True, debug=True)