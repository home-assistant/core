"""
Support for a wall all tts device
"""
import os
from wallall import wallall
import voluptuous as vol
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS,CONF_HOST, CONF_PORT,
    STATE_UNKNOWN, ATTR_ATTRIBUTION)

from homeassistant.components.tts import Provider, PLATFORM_SCHEMA, CONF_LANG

REQUIREMENTS = ['wallall==0.7']
def get_engine(hass, config):
    """Set up wallall speech component."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    lang = config.get(CONF_LANG)
    wllDevice = wallall.WallAllCtx("{0}:{1}".format(host, port))
    return WallAllTTS(lang)

SUPPORT_LANGUAGES = [
    'af', 'sq', 'ar', 'hy', 'bn', 'ca', 'zh', 'zh-cn', 'zh-tw', 'zh-yue',
    'hr', 'cs', 'da', 'nl', 'en', 'en-au', 'en-uk', 'en-us', 'eo', 'fi',
    'fr', 'de', 'el', 'hi', 'hu', 'is', 'id', 'it', 'ja', 'ko', 'la', 'lv',
    'mk', 'no', 'pl', 'pt', 'pt-br', 'ro', 'ru', 'sr', 'sk', 'es', 'es-es',
    'es-us', 'sw', 'sv', 'ta', 'th', 'tr', 'vi', 'cy', 'uk',
]

class WallAllTTS(Provider):
    """WallAll Device speech API provider."""

    def __init__(self, lang):
        """Initialize demo provider."""
        self._lang = lang
        self.name = 'WallAllTTS'
    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self):
        """Return list of supported options like voice, emotionen."""
        return ['voice', 'age']

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from demo."""
        wllDevice.speak(message)

        return ('mp3', None)
