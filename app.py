from flask import Flask, jsonify, render_template, send_from_directory, request
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
import os
import logging
from werkzeug.serving import WSGIRequestHandler
from datetime import datetime
from streaming_tts import tts_service

# Configure Werkzeug logging
WSGIRequestHandler.protocol_version = "HTTP/1.1"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_requests.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder='static', template_folder='templates')
app.wsgi_app = ProxyFix(app.wsgi_app)

# Flag to toggle between audio/stream and audio/speech
USE_STREAM_ENDPOINT = True

@app.route('/')
def index():
    logger.info('Index page accessed')
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/get_ephemeral_token', methods=['GET', 'POST'])
def get_ephemeral_token():
    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-realtime-preview-2024-12-17",
        "voice": "verse"
    }
    
    # If POST request with session_id
    if request.method == 'POST':
        try:
            session_data = request.get_json()
            if session_data and session_data.get('session_id'):
                data['session_id'] = session_data['session_id']
        except Exception as e:
            logger.error(f"Error parsing POST data: {str(e)}")
    
    try:
        logger.info(f"Requesting ephemeral token at {datetime.now()}")
        logger.debug(f"Request headers: {headers}")
        logger.debug(f"Request data: {data}")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        logger.info("Ephemeral token received successfully")
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting ephemeral token: {str(e)}")
        if hasattr(e.response, 'json'):
            error_details = e.response.json()
            logger.error(f"API Error response: {error_details}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/get_speech', methods=['POST'])
def get_speech():
    text = request.json.get('text')
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    try:
        if USE_STREAM_ENDPOINT:
            audio_data = tts_service.get_stream(text)
        else:
            audio_data = tts_service.get_speech(text)
        
        if audio_data:
            return audio_data, 200, {'Content-Type': 'audio/mpeg'}
        else:
            return jsonify({"error": "Failed to generate speech"}), 500
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False)
