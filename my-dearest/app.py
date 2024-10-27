import os
import io
import asyncio
import queue
import threading
import aiohttp
import logging
from flask import Flask, render_template, send_from_directory, request, send_file, jsonify
from flask_socketio import SocketIO, emit, Namespace
from openai import AsyncOpenAI
import webrtcvad
import wave
import time
from streaming_tts import stream_tts
from dotenv import load_dotenv
import asyncio
import engineio
load_dotenv()
# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class AudioNamespace(Namespace):
    def on_connect(self):
        logging.info('Client connected to audio namespace')

    def on_disconnect(self):
        logging.info('Client disconnected from audio namespace')

    def on_audio_data(self, data):
        if isinstance(data, bytes):
            handle_audio_data(data)
        else:
            logging.error(f"Received non-binary audio data: {type(data)}")


API_BASE_URL = "https://api.sws.speechify.com"
API_KEY = os.getenv("SP_API_KEY")
VOICE_ID = "28c4d41d-8811-4ca0-9515-377d6ca2c715"

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

conversation_history = []
conversation_active = False
vad = webrtcvad.Vad(3)  # Aggressiveness mode (0-3)

USE_STREAMING_TTS = True

SYSTEM_PROMPT = ("You are a calm, soothing assistant who speaks in a warm, empathetic, and gentle manner. "
                 "Your responses should make the user feel heard and understood, similar to a therapist. "
                 "Always provide thoughtful and reflective answers that help the user feel comforted.")

COOLDOWN_PERIOD = float(os.getenv('COOLDOWN_PERIOD', 0))

is_speaking = False
tts_queue = queue.Queue()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/beep')
def serve_beep():
    return send_from_directory('static/audio', 'beep.mp3', mimetype='audio/mpeg')

@socketio.on('connect')
def handle_connect():
    logging.info('Client connected')
    emit('connection_established')

@socketio.on('disconnect')
def handle_disconnect():
    logging.info('Client disconnected')

last_response_time = 0

@socketio.on('transcription')
def handle_transcription(transcription):
    global conversation_active, last_response_time, is_speaking
    try:
        if is_speaking:
            logging.info("System is speaking. Ignoring input.")
            return

        current_time = time.time()
        if current_time - last_response_time < COOLDOWN_PERIOD:
            logging.info(f"Cooldown period active. Ignoring transcription: {transcription}")
            return

        logging.info(f"Received transcription: {transcription}")
        if not conversation_active:
            conversation_active = True
            emit('conversation_started')

        asyncio.run(process_command(transcription))
        last_response_time = current_time
    except Exception as e:
        logging.error(f"Error in handle_transcription: {str(e)}")
        emit('error', {'message': 'An error occurred while processing your request.'})

async def process_command(command):
    global is_speaking
    conversation_history.append({"role": "user", "content": command})
    is_speaking = True
    emit('system_speaking', {'speaking': True})

    if USE_STREAMING_TTS:
        await stream_response(conversation_history)
    else:
        response = await get_ai_response(conversation_history)
        emit('ai_response', {'text': response, 'is_final': True})
        audio_url = await generate_audio(response)
        emit('audio_response', {'url': audio_url})

    is_speaking = False
    emit('system_speaking', {'speaking': False})

def tts_worker():
    logging.info("TTS worker started")
    while True:
        text = tts_queue.get()
        if text is None:
            logging.info("TTS worker stopping")
            break
        logging.info(f"Processing TTS for text: {text}")
        audio_stream = stream_tts(text)
        if audio_stream:
            for audio_chunk in audio_stream:
                socketio.emit('audio_chunk', {'chunk': audio_chunk})
        tts_queue.task_done()

async def stream_response(conversation):
    try:
        logging.info("Starting stream_response")
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
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
                logging.info(f"Received content chunk: {content}")
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

    except Exception as e:
        logging.error(f"Error in stream_response: {str(e)}")
        emit('ai_response', {'text': "Sorry, there was an error processing your request.", 'is_final': True})
        emit('response_complete')

@socketio.on('audio_data')
def handle_audio_data(data):
    global is_speaking
    try:
        if is_speaking:
            return

        # Input validation
        if not data:
            logging.debug("Received empty audio data")
            emit('speech_detected', {'detected': False})
            return

        # Convert string data to bytes if needed
        audio_data = data
        if isinstance(audio_data, str):
            try:
                audio_data = audio_data.encode('utf-8')
            except UnicodeEncodeError as e:
                logging.error(f"Error encoding audio data: {str(e)}")
                emit('speech_detected', {'detected': False})
                return

        # Validate audio data length
        if len(audio_data) < 1024:  # Minimum reasonable size for audio frame
            logging.debug(f"Audio data too short: {len(audio_data)} bytes")
            emit('speech_detected', {'detected': False})
            return

        # Log successful processing
        logging.debug(f"Processing audio data: type={type(audio_data)}, length={len(audio_data)}")

        speech_detected = is_speech(audio_data)
        emit('speech_detected', {'detected': speech_detected})

        if speech_detected:
            logging.debug("Speech detected in audio frame")

    except Exception as e:
        logging.error(f"Error in handle_audio_data: {str(e)}")
        emit('speech_detected', {'detected': False})


def is_speech(audio_data):
    try:
        sample_rate = 16000
        frame_duration = 30  # in milliseconds
        frame_size = int(sample_rate * (frame_duration / 1000.0))
        logging.debug(f"Expected frame size: {frame_size} bytes for {frame_duration} ms at {sample_rate} Hz")

        # Ensure audio data length is valid
        if len(audio_data) < frame_size:
            logging.debug(f"Audio frame too short: {len(audio_data)} bytes")
            return False

        # Ensure we have the correct number of bytes for 16-bit audio
        if len(audio_data) % 2 != 0:
            logging.debug("Received odd number of bytes for 16-bit audio")
            return False

        offset = 0
        speech_detected = False

        while offset + frame_size <= len(audio_data):
            frame = audio_data[offset:offset + frame_size]

            try:
                # Check if we have a complete frame
                if len(frame) == frame_size:
                    is_speech = vad.is_speech(frame, sample_rate)
                    if is_speech:
                        speech_detected = True
                        break
            except Exception as frame_error:
                logging.debug(f"Error processing specific frame: {str(frame_error)}")
                logging.debug(f"Frame data length: {len(frame)}, Frame data type: {type(frame)}")
                # Continue with next frame instead of failing completely
                pass

            offset += frame_size

        return speech_detected

    except Exception as e:
        logging.error(f"Error in is_speech: {str(e)}")
        # Log the audio data details for debugging
        logging.debug(f"Audio data type: {type(audio_data)}, length: {len(audio_data)}")
        return False

async def get_ai_response(conversation):
    logging.info("Sending request to OpenAI")
    try:
        full_conversation = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ] + conversation
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=full_conversation,
            stream=True
        )

        collected_messages = []
        async for chunk in response:
            if chunk.choices[0].delta.content is not None:
                collected_messages.append(chunk.choices[0].delta.content)
                full_reply_content = ''.join(collected_messages).strip()
                logging.info(f"Emitting partial response: {full_reply_content}")
                emit('ai_response', {'text': full_reply_content, 'is_final': False})

        full_reply_content = ''.join(collected_messages).strip()
        conversation_history.append({"role": "assistant", "content": full_reply_content})
        return full_reply_content
    except Exception as e:
        logging.error(f"Error in get_ai_response: {str(e)}")
        return "Sorry, there was an error processing your request."

async def generate_audio(text):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE_URL}/v1/audio/stream", json={
                "input": f"{text}",
                "voice_id": VOICE_ID,
            }, headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }) as response:
                if response.status == 200:
                    return f"/stream_audio?text={text}"
                else:
                    logging.error(f"Failed to generate audio: {response.status}")
                    logging.error(f"Response content: {await response.text()}")
                    return None
    except Exception as e:
        logging.error(f"Error in generate_audio: {str(e)}")
        return None

@app.route('/stream_audio')
async def stream_audio():
    text = request.args.get('text')
    if not text:
        return jsonify({"error": "No text provided"}), 400
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE_URL}/v1/audio/stream", json={
                "input": f"{text}",
                "voice_id": VOICE_ID,
            }, headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }) as response:
                if response.status == 200:
                    audio_stream = io.BytesIO(await response.read())
                    return send_file(audio_stream, mimetype='audio/mpeg')
                else:
                    return jsonify({"error": "Failed to stream audio"}), response.status
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@socketio.on('ping')
def handle_ping():
    emit('pong')

if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug=True, debug=True, use_reloader=False)
