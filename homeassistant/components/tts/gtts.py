"""
Support for Google TTS in Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts.gtts/
"""

import logging

from homeassistant.components.tts import BaseTTSService

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['gTTS==1.1.4']


def get_engine(hass, config):
    """Get the gTTS TTS service."""
    return GTTSService()


# pylint: disable=too-few-public-methods
class GTTSService(BaseTTSService):
    """Implement the TTS service for gTTS."""

    def __init__(self):
        """Initialize the service."""

    # pylint: disable=too-many-arguments
    def get_speech(self, file_path, text, language=None, rate=None,
                   codec=None, audio_format=None):
        """Generate an audio file from gTTS for the text."""
        from gtts import gTTS
        tts = gTTS(text=text, lang=language)
        tts.save(file_path)
