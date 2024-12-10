# conversation_manager.py
import logging
from datetime import datetime
import json
import openai
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
log_filename = os.path.join('logs', f"conversation_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConversationManager:
    def __init__(self):
        self.session_id = None
        self.conversation_history = []
        self.is_active = False
        self.current_audio_stream = None
        self.binary_buffer = bytearray()
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def start_session(self):
        try:
            self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.is_active = True
            self.conversation_history = []
            logger.info(f"Started new session: {self.session_id}")
            return self.session_id
        except Exception as e:
            logger.error(f"Error starting session: {str(e)}")
            return None

    def add_binary_chunk(self, chunk):
        try:
            MAX_BUFFER_SIZE = 16000 * 5  # 5 seconds of audio
            if len(self.binary_buffer) + len(chunk) > MAX_BUFFER_SIZE:
                logger.info("Buffer full, processing current chunk")
                print("Buffer full, processing current chunk")
                return True
            self.binary_buffer.extend(chunk)
            return False
        except Exception as e:
            logger.error(f"Error adding binary chunk: {str(e)}")
            return False

    def get_binary_buffer(self):
        return bytes(self.binary_buffer)

    def clear_binary_buffer(self):
        self.binary_buffer = bytearray()

    def add_to_history(self, speaker, message):
        try:
            self.conversation_history.append({
                'timestamp': datetime.now().isoformat(),
                'speaker': speaker,
                'message': message
            })
        except Exception as e:
            logger.error(f"Error adding to history: {str(e)}")

    def get_conversation_context(self):
        try:
            return self.conversation_history[-5:] if self.conversation_history else []
        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return []

    def generate_response(self, user_message):
        try:
            self.add_to_history("user", user_message)

            messages = [
                {"role": "system", "content": "You are a calm, empathetic, and enthusiastic assistant."}
            ]

            for msg in self.get_conversation_context():
                messages.append({
                    "role": "user" if msg["speaker"] == "user" else "assistant",
                    "content": msg["message"]
                })

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages
            )

            ai_response = response.choices[0].message.content
            self.add_to_history("assistant", ai_response)
            logger.info(f"Generated AI response: {ai_response}")
            return ai_response

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return None

    def end_session(self):
        try:
            self.is_active = False
            self.clear_binary_buffer()
            logger.info(f"Ended session: {self.session_id}")
            return True
        except Exception as e:
            logger.error(f"Error ending session: {str(e)}")
            return False


# Singleton instance
conversation_manager = ConversationManager()