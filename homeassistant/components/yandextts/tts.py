"""Support for the yandex speechkit tts  service."""
import asyncio
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

YANDEX_API_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

SUPPORT_LANGUAGES = ["ru-RU", "en-US", "tr-TR"]

SUPPORT_CODECS = ["lpcm", "oggopus"]

SUPPORT_VOICES = [
    "oksana",
    "jane",
    "omazh",
    "zahar",
    "ermil",
    "silaerkan",
    "erkanyavas",
    "alyss",
    "nick",
    "alena",
    "filipp"
]

SUPPORTED_EMOTION = ["good", "evil", "neutral"]

MIN_SPEED = 0.1
MAX_SPEED = 3

CONF_CODEC = "codec"
CONF_VOICE = "voice"
CONF_EMOTION = "neutral"
CONF_SPEED = "speed"

DEFAULT_LANG = "en-US"
DEFAULT_CODEC = "oggopus"
DEFAULT_VOICE = "omazh"
DEFAULT_EMOTION = "neutral"
DEFAULT_SPEED = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_CODEC, default=DEFAULT_CODEC): vol.In(SUPPORT_CODECS),
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): vol.In(SUPPORT_VOICES),
        vol.Optional(CONF_EMOTION, default=DEFAULT_EMOTION): vol.In(SUPPORTED_EMOTION),
        vol.Optional(CONF_SPEED, default=DEFAULT_SPEED): vol.Range(
            min=MIN_SPEED, max=MAX_SPEED
        ),
    }
)

SUPPORTED_OPTIONS = [CONF_CODEC, CONF_VOICE, CONF_EMOTION, CONF_SPEED]


async def async_get_engine(hass, config):
    """Set up VoiceRSS speech component."""
    return YandexSpeechKitProvider(hass, config)


class YandexSpeechKitProvider(Provider):
    """VoiceRSS speech api provider."""

    def __init__(self, hass, conf):
        """Init VoiceRSS TTS service."""
        self.hass = hass
        self._codec = conf.get(CONF_CODEC)
        self._key = conf.get(CONF_API_KEY)
        self._speaker = conf.get(CONF_VOICE)
        self._language = conf.get(CONF_LANG)
        self._emotion = conf.get(CONF_EMOTION)
        self._speed = str(conf.get(CONF_SPEED))
        self.name = "YandexSpeechKit"

    @property
    def default_language(self):
        """Return the default language."""
        return self._language

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self):
        """Return list of supported options."""
        return SUPPORTED_OPTIONS

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from yandex speechkit."""
        websession = async_get_clientsession(self.hass)
        actual_language = language
        options = options or {}

        try:
            with async_timeout.timeout(10):
                url_param = {
                    "text": message,
                    "lang": actual_language,
                    "voice": options.get(CONF_VOICE, self._speaker),
                    "format": options.get(CONF_CODEC, self._codec),
                    "emotion": options.get(CONF_EMOTION, self._emotion),
                    "speed": options.get(CONF_SPEED, self._speed),
                }

                bearer__format = "Api-Key {}".format(self._key)
                request = await websession.post(YANDEX_API_URL,
                                                headers={"authorization": bearer__format},
                                                data=url_param
                                                )

                if request.status != 200:
                    error = await request.read()
                    _LOGGER.error(
                        "Error %d on load URL %s. Response %s", request.status, request.url, error
                    )
                    return (None, None)
                data = await request.read()

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout for yandex speech kit API")
            return (None, None)

        return (self._codec, data)
