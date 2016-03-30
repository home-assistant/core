"""
Support for VoiceRSS TTS in Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts.voicerss/
"""

import logging
import shutil
import requests

from homeassistant.helpers import validate_config
from homeassistant.components.tts import (DOMAIN, BaseTTSService)

_LOGGER = logging.getLogger(__name__)


def get_engine(hass, config):
    """Get the VoiceRSS TTS service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['key']},
                           _LOGGER):
        return None

    return VoiceRSSService(config['key'])


# pylint: disable=too-few-public-methods
class VoiceRSSService(BaseTTSService):
    """Implement the TTS service for VoiceRSS."""

    def __init__(self, api_key):
        """Initialize the service."""
        self.api_key = api_key

    # pylint: disable=too-many-arguments
    def get_speech(self, file_path, text, language=None, rate=None,
                   codec=None, audio_format=None):
        """Generate an audio file from VoiceRSS for the text."""
        if language is None:
            language = 'en-us'
        else:
            language = language.lower()
        if rate is None:
            rate = 0
        if codec is None:
            codec = 'MP3'
        if audio_format is None:
            audio_format = '44khz_16bit_stereo'

        payload = {'key': self.api_key, 'src': text, 'hl': language,
                   'r': rate, 'c': codec, 'f': audio_format}
        tts_file = requests.get("https://api.voicerss.org/",
                                stream=True, params=payload)
        if tts_file.status_code == 200:
            with open(file_path, 'wb') as opened_file:
                tts_file.raw.decode_content = True
                shutil.copyfileobj(tts_file.raw, opened_file)
        else:
            err = "An error occurred when requesting a file from VoiceRSS!"
            _LOGGER.error(err)
