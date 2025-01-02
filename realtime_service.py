import os
import logging
from dotenv import load_dotenv
import requests
from logging_config import setup_logging

logger = setup_logging('realtime_service')

class RealtimeService:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        logger.info("Realtime service initialized")
        logger.debug(f"API Key present: {'Yes' if self.api_key else 'No'}")

def create_ephemeral_token(api_key):
    try:
        url = "https://api.openai.com/v1/realtime/sessions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o-realtime-preview-2024-12-17",
            "voice": "verse"
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        token = response.json()['client_secret']['value']
        logger.info("Ephemeral token created successfully")
        return token
    except Exception as e:
        logger.error(f"Error creating ephemeral token: {str(e)}", exc_info=True)
        raise

# Singleton instance
realtime_service = RealtimeService()
