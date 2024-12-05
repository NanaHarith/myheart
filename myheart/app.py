import os
import io
import asyncio
import aiohttp
import logging
from flask import Flask, render_template, send_from_directory, request, send_file, jsonify
from flask_socketio import SocketIO, emit
from openai import AsyncOpenAI
import time
from streaming_tts import stream_tts
from dotenv import load_dotenv
import threading
import queue
import numpy as np
import torch

# Import Silero VAD
from silero_vad import SileroVAD

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "https://api.sws.speechify.com"
API_KEY = os.getenv("SP_API_KEY")
VOICE_ID = "28c4d41d-8811-4ca0-9515-377d6ca2c715"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Application Setup
app = Flask(__name__)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    binary=True,
    logger=True,
    engineio_logger=True,
    max_http_buffer_size=1024 * 1024  # 1MB buffer
)

# Global Variables
client = AsyncOpenAI(api_key=OPENAI_API_KEY)
conversation_history = []
conversation_active = False
is_speaking = False
tts_queue = queue.Queue()

# Initialize VAD
vad = SileroVAD(threshold=0.5)

# System Prompt
SYSTEM_PROMPT = (
    "You are a calm, empathetic AI assistant who provides thoughtful, "
    "nuanced responses. Speak gently and help users feel understood."
)


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('transcription')
def handle_transcription(transcription):
    global conversation_active, is_speaking
    try:
        if is_speaking:
            logger.info("System is speaking. Ignoring input.")
            return

        logger.info(f"Received transcription: {transcription}")
        if not conversation_active:
            conversation_active = True
            emit('conversation_started')

        asyncio.run(process_command(transcription))
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        emit('error', {'message': 'Processing error'})


async def process_command(command):
    global is_speaking
    conversation_history.append({"role": "user", "content": command})
    is_speaking = True
    emit('system_speaking', {'speaking': True})

    try:
        await stream_response(conversation_history)
    except Exception as e:
        logger.error(f"Command processing error: {e}")
        emit('ai_response', {'text': "I'm experiencing difficulties.", 'is_final': True})
    finally:
        is_speaking = False
        emit('system_speaking', {'speaking': False})


def tts_worker():
    while True:
        text = tts_queue.get()
        if text is None:
            break

        audio_stream = stream_tts(text)
        if audio_stream:
            for audio_chunk in audio_stream:
                socketio.emit('audio_chunk', {'chunk': audio_chunk})
        tts_queue.task_done()


async def stream_response(conversation):
    response = await client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation,
        stream=True
    )

    tts_thread = threading.Thread(target=tts_worker)
    tts_thread.start()

    collected_messages = []
    batched_content = ""
    async for chunk in response:
        if chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            collected_messages.append(content)
            batched_content += content

            full_reply_content = ''.join(collected_messages).strip()
            emit('ai_response', {'text': full_reply_content, 'is_final': False})

            if len(batched_content) >= 40:
                tts_queue.put(batched_content)
                batched_content = ""

    if batched_content:
        tts_queue.put(batched_content)

    full_reply_content = ''.join(collected_messages).strip()
    conversation_history.append({"role": "assistant", "content": full_reply_content})
    emit('ai_response', {'text': full_reply_content, 'is_final': True})

    tts_queue.join()
    tts_queue.put(None)
    tts_thread.join()

    emit('response_complete')


@socketio.on('audio_data')
def handle_audio_data(audio_data):
    """
    Handle incoming audio data for VAD detection.
    """
    global is_speaking

    if is_speaking:
        return

    try:
        # Convert raw audio bytes to a numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        audio_float = audio_array.astype(np.float32) / 32768.0

        # Run speech detection
        speech_detected = vad.is_speech(audio_float, sample_rate=16000)

        # Emit VAD results to client
        emit('speech_detected', {'detected': speech_detected})
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        emit('speech_detected', {'detected': False})


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
