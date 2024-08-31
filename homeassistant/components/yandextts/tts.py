"""Support for the yandex speechkit tts  service."""
import asyncio
from http import HTTPStatus
import logging

import aiohttp
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

YANDEX_API_URL = "https://tts.voicetech.yandex.net/generate?"

SUPPORT_LANGUAGES = ["ru-RU", "en-US", "tr-TR", "uk-UK"]

SUPPORT_CODECS = ["mp3", "wav", "opus"]

SUPPORT_VOICES = [
    "jane",
    "oksana",
    "alyss",
    "omazh",
    "zahar",
    "ermil",
    "levitan",
    "ermilov",
    "silaerkan",
    "kolya",
    "kostya",
    "nastya",
    "sasha",
    "nick",
    "erkanyavas",
    "zhenya",
    "tanya",
    "anton_samokhvalov",
    "tatyana_abramova",
    "voicesearch",
    "ermil_with_tuning",
    "robot",
    "dude",
    "zombie",
    "smoky",
]

SUPPORTED_EMOTION = ["good", "evil", "neutral"]

MIN_SPEED = 0.1
MAX_SPEED = 3

CONF_CODEC = "codec"
CONF_VOICE = "voice"
CONF_EMOTION = "emotion"
CONF_SPEED = "speed"

DEFAULT_LANG = "en-US"
DEFAULT_CODEC = "mp3"
DEFAULT_VOICE = "zahar"
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


async def async_get_engine(hass, config, discovery_info=None):
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
        self.name = "YandexTTS"

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

    async def async_get_tts_audio(self, message, language, options):
        """Load TTS from yandex."""
        websession = async_get_clientsession(self.hass)
        actual_language = language

        try:
            async with asyncio.timeout(10):
                url_param = {
                    "text": message,
                    "lang": actual_language,
                    "key": self._key,
                    "speaker": options.get(CONF_VOICE, self._speaker),
                    "format": options.get(CONF_CODEC, self._codec),
                    "emotion": options.get(CONF_EMOTION, self._emotion),
                    "speed": options.get(CONF_SPEED, self._speed),
                }

                request = await websession.get(YANDEX_API_URL, params=url_param)

                if request.status != HTTPStatus.OK:
                    _LOGGER.error(
                        "Error %d on load URL %s", request.status, request.url
                    )
                    return (None, None)
                data = await request.read()

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout for yandex speech kit API")
            return (None, None)

        return (self._codec, data)
