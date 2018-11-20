"""
Support for the MaryTTS service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts.marytts/
"""
import asyncio
import logging
import re

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.components.tts import Provider, PLATFORM_SCHEMA, CONF_LANG
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORT_LANGUAGES = [
    'de', 'en-GB', 'en-US', 'fr', 'it', 'lb', 'ru', 'sv', 'te', 'tr'
]

SUPPORT_CODEC = [
    'aiff', 'au', 'wav'
]

CONF_VOICE = 'voice'
CONF_CODEC = 'codec'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 59125
DEFAULT_LANG = 'en-US'
DEFAULT_VOICE = 'cmu-slt-hsmm'
DEFAULT_CODEC = 'wav'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
    vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): cv.string,
    vol.Optional(CONF_CODEC, default=DEFAULT_CODEC): vol.In(SUPPORT_CODEC)
})


async def async_get_engine(hass, config):
    """Set up MaryTTS speech component."""
    return MaryTTSProvider(hass, config)


class MaryTTSProvider(Provider):
    """MaryTTS speech api provider."""

    def __init__(self, hass, conf):
        """Init MaryTTS TTS service."""
        self.hass = hass
        self._host = conf.get(CONF_HOST)
        self._port = conf.get(CONF_PORT)
        self._codec = conf.get(CONF_CODEC)
        self._voice = conf.get(CONF_VOICE)
        self._language = conf.get(CONF_LANG)
        self.name = 'MaryTTS'

    @property
    def default_language(self):
        """Return the default language."""
        return self._language

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from MaryTTS."""
        websession = async_get_clientsession(self.hass)

        actual_language = re.sub('-', '_', language)

        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                url = 'http://{}:{}/process?'.format(self._host, self._port)

                audio = self._codec.upper()
                if audio == 'WAV':
                    audio = 'WAVE'

                url_param = {
                    'INPUT_TEXT': message,
                    'INPUT_TYPE': 'TEXT',
                    'AUDIO': audio,
                    'VOICE': self._voice,
                    'OUTPUT_TYPE': 'AUDIO',
                    'LOCALE': actual_language
                }

                request = await websession.get(url, params=url_param)

                if request.status != 200:
                    _LOGGER.error("Error %d on load url %s",
                                  request.status, request.url)
                    return (None, None)
                data = await request.read()

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout for MaryTTS API")
            return (None, None)

        return (self._codec, data)
