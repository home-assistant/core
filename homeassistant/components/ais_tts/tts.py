"""Support for the AIS speech service."""
import os
import logging

import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider

SUPPORT_LANGUAGES = ['pl', 'en']
_LOGGER = logging.getLogger(__name__)
DEFAULT_LANG = 'pl'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
})


async def async_get_engine(hass, config):
    """Set up AIS speech component."""
    return AisTTSProvider(hass, config)


class AisTTSProvider(Provider):
    """AIS speech api provider."""

    def __init__(self, hass, conf):
        """Init MaryTTS TTS service."""
        self.name = 'AisTTS'

    @property
    def default_language(self):
        """Return the default language."""
        return DEFAULT_LANG

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES


    @property
    def supported_options(self):
        """Return a list of supported options like voice, emotionen."""
        return None

    @property
    def default_options(self):
        """Return a dict include default options."""
        return None

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from AisTTS."""
        await self.hass.services.async_call('ais_ai_service', 'say_it', {"text": message})
        # filename = os.path.join(os.path.dirname(__file__), 'tts.mp3')
        # try:
        #     with open(filename, 'rb') as voice:
        #         data = voice.read()
        # except OSError:
        #     return (None, None)
        #
        # return ('mp3', data)
        return None, None
