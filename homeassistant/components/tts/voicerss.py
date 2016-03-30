"""
Support for VoiceRSS TTS in Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts.voicerss/
"""

import logging
import shutil
import urllib.parse
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
    def speak(self, file_path, text, language, rate, codec, audio_format):
        """Generate an audio file from VoiceRSS for the text."""
        params = urllib.parse.urlencode({'key': self.api_key, 'src': text,
                                         'hl': language, 'r': rate,
                                         'c': codec, 'f': audio_format})
        url = "https://api.voicerss.org/?{}".format(params)
        tts_file = requests.get(url, stream=True)
        if tts_file.status_code == 200:
            with open(file_path, 'wb') as opened_file:
                tts_file.raw.decode_content = True
                shutil.copyfileobj(tts_file.raw, opened_file)
        else:
            err = "An error occurred when requesting a file from VoiceRSS!"
            _LOGGER.error(err)
