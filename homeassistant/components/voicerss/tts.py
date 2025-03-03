"""Support for the voicerss speech service."""

import asyncio
from http import HTTPStatus
import logging

import aiohttp
import voluptuous as vol

from homeassistant.components.tts import (
    CONF_LANG,
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

VOICERSS_API_URL = "https://api.voicerss.org/"

ERROR_MSG = [
    b"Error description",
    b"The subscription is expired or requests count limitation is exceeded!",
    b"The request content length is too large!",
    b"The language does not support!",
    b"The language is not specified!",
    b"The text is not specified!",
    b"The API key is not available!",
    b"The API key is not specified!",
    b"The subscription does not support SSML!",
]

SUPPORT_LANGUAGES = [
    "ar-eg",
    "ar-sa",
    "bg-bg",
    "ca-es",
    "zh-cn",
    "zh-hk",
    "zh-tw",
    "hr-hr",
    "cs-cz",
    "da-dk",
    "nl-be",
    "nl-nl",
    "en-au",
    "en-ca",
    "en-gb",
    "en-in",
    "en-ie",
    "en-us",
    "fi-fi",
    "fr-ca",
    "fr-fr",
    "fr-ch",
    "de-at",
    "de-de",
    "de-ch",
    "el-gr",
    "he-il",
    "hi-in",
    "hu-hu",
    "id-id",
    "it-it",
    "ja-jp",
    "ko-kr",
    "ms-my",
    "nb-no",
    "pl-pl",
    "pt-br",
    "pt-pt",
    "ro-ro",
    "ru-ru",
    "sk-sk",
    "sl-si",
    "es-mx",
    "es-es",
    "sv-se",
    "ta-in",
    "th-th",
    "tr-tr",
    "vi-vn",
]

SUPPORT_CODECS = ["mp3", "wav", "aac", "ogg", "caf"]  # codespell:ignore caf

SUPPORT_FORMATS = [
    "8khz_8bit_mono",
    "8khz_8bit_stereo",
    "8khz_16bit_mono",
    "8khz_16bit_stereo",
    "11khz_8bit_mono",
    "11khz_8bit_stereo",
    "11khz_16bit_mono",
    "11khz_16bit_stereo",
    "12khz_8bit_mono",
    "12khz_8bit_stereo",
    "12khz_16bit_mono",
    "12khz_16bit_stereo",
    "16khz_8bit_mono",
    "16khz_8bit_stereo",
    "16khz_16bit_mono",
    "16khz_16bit_stereo",
    "22khz_8bit_mono",
    "22khz_8bit_stereo",
    "22khz_16bit_mono",
    "22khz_16bit_stereo",
    "24khz_8bit_mono",
    "24khz_8bit_stereo",
    "24khz_16bit_mono",
    "24khz_16bit_stereo",
    "32khz_8bit_mono",
    "32khz_8bit_stereo",
    "32khz_16bit_mono",
    "32khz_16bit_stereo",
    "44khz_8bit_mono",
    "44khz_8bit_stereo",
    "44khz_16bit_mono",
    "44khz_16bit_stereo",
    "48khz_8bit_mono",
    "48khz_8bit_stereo",
    "48khz_16bit_mono",
    "48khz_16bit_stereo",
    "alaw_8khz_mono",
    "alaw_8khz_stereo",
    "alaw_11khz_mono",
    "alaw_11khz_stereo",
    "alaw_22khz_mono",
    "alaw_22khz_stereo",
    "alaw_44khz_mono",
    "alaw_44khz_stereo",
    "ulaw_8khz_mono",
    "ulaw_8khz_stereo",
    "ulaw_11khz_mono",
    "ulaw_11khz_stereo",
    "ulaw_22khz_mono",
    "ulaw_22khz_stereo",
    "ulaw_44khz_mono",
    "ulaw_44khz_stereo",
]

CONF_CODEC = "codec"
CONF_FORMAT = "format"

DEFAULT_LANG = "en-us"
DEFAULT_CODEC = "mp3"
DEFAULT_FORMAT = "8khz_8bit_mono"


PLATFORM_SCHEMA = TTS_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_CODEC, default=DEFAULT_CODEC): vol.In(SUPPORT_CODECS),
        vol.Optional(CONF_FORMAT, default=DEFAULT_FORMAT): vol.In(SUPPORT_FORMATS),
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up VoiceRSS TTS component."""
    return VoiceRSSProvider(hass, config)


class VoiceRSSProvider(Provider):
    """The VoiceRSS speech API provider."""

    def __init__(self, hass, conf):
        """Init VoiceRSS TTS service."""
        self.hass = hass
        self._extension = conf[CONF_CODEC]
        self._lang = conf[CONF_LANG]
        self.name = "VoiceRSS"

        self._form_data = {
            "key": conf[CONF_API_KEY],
            "hl": conf[CONF_LANG],
            "c": (conf[CONF_CODEC]).upper(),
            "f": conf[CONF_FORMAT],
        }

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    async def async_get_tts_audio(self, message, language, options):
        """Load TTS from VoiceRSS."""
        websession = async_get_clientsession(self.hass)
        form_data = self._form_data.copy()

        form_data["src"] = message
        form_data["hl"] = language

        try:
            async with asyncio.timeout(10):
                request = await websession.post(VOICERSS_API_URL, data=form_data)

                if request.status != HTTPStatus.OK:
                    _LOGGER.error(
                        "Error %d on load url %s", request.status, request.url
                    )
                    return (None, None)
                data = await request.read()

                if data in ERROR_MSG:
                    _LOGGER.error("Error receive %s from VoiceRSS", str(data, "utf-8"))
                    return (None, None)

        except (TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout for VoiceRSS API")
            return (None, None)

        return (self._extension, data)
