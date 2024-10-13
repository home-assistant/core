"""Support for Baidu speech service."""

import logging

from aip import AipSpeech
import voluptuous as vol

from homeassistant.components.tts import (
    CONF_LANG,
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["zh"]
DEFAULT_LANG = "zh"
SUPPORTED_PERSON = [0, 1, 3, 4, 5, 103, 106, 110, 111, 5003, 5118]

CONF_APP_ID = "app_id"
CONF_SECRET_KEY = "secret_key"
CONF_SPEED = "speed"
CONF_PITCH = "pitch"
CONF_VOLUME = "volume"
CONF_PERSON = "person"

PLATFORM_SCHEMA = TTS_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
        vol.Required(CONF_APP_ID): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SECRET_KEY): cv.string,
        vol.Optional(CONF_SPEED, default=5): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=9)
        ),
        vol.Optional(CONF_PITCH, default=5): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=9)
        ),
        vol.Optional(CONF_VOLUME, default=5): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=15)
        ),
        vol.Optional(CONF_PERSON, default=0): vol.In(SUPPORTED_PERSON),
    }
)

# Keys are options in the config file, and Values are options
# required by Baidu TTS API.
_OPTIONS = {
    CONF_PERSON: "per",
    CONF_PITCH: "pit",
    CONF_SPEED: "spd",
    CONF_VOLUME: "vol",
}
SUPPORTED_OPTIONS = [CONF_PERSON, CONF_PITCH, CONF_SPEED, CONF_VOLUME]


def get_engine(hass, config, discovery_info=None):
    """Set up Baidu TTS component."""
    return BaiduTTSProvider(hass, config)


class BaiduTTSProvider(Provider):
    """Baidu TTS speech api provider."""

    def __init__(self, hass, conf):
        """Init Baidu TTS service."""
        self.hass = hass
        self._lang = conf[CONF_LANG]
        self._codec = "mp3"
        self.name = "BaiduTTS"

        self._app_data = {
            "appid": conf[CONF_APP_ID],
            "apikey": conf[CONF_API_KEY],
            "secretkey": conf[CONF_SECRET_KEY],
        }

        self._speech_conf_data = {
            _OPTIONS[CONF_PERSON]: conf[CONF_PERSON],
            _OPTIONS[CONF_PITCH]: conf[CONF_PITCH],
            _OPTIONS[CONF_SPEED]: conf[CONF_SPEED],
            _OPTIONS[CONF_VOLUME]: conf[CONF_VOLUME],
        }

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def default_options(self):
        """Return a dict including default options."""
        return {
            CONF_PERSON: self._speech_conf_data[_OPTIONS[CONF_PERSON]],
            CONF_PITCH: self._speech_conf_data[_OPTIONS[CONF_PITCH]],
            CONF_SPEED: self._speech_conf_data[_OPTIONS[CONF_SPEED]],
            CONF_VOLUME: self._speech_conf_data[_OPTIONS[CONF_VOLUME]],
        }

    @property
    def supported_options(self):
        """Return a list of supported options."""
        return SUPPORTED_OPTIONS

    def get_tts_audio(self, message, language, options):
        """Load TTS from BaiduTTS."""

        aip_speech = AipSpeech(
            self._app_data["appid"],
            self._app_data["apikey"],
            self._app_data["secretkey"],
        )

        speech_data = self._speech_conf_data.copy()
        for key, value in options.items():
            speech_data[_OPTIONS[key]] = value

        result = aip_speech.synthesis(message, language, 1, speech_data)

        if isinstance(result, dict):
            _LOGGER.error(
                "Baidu TTS error-- err_no:%d; err_msg:%s; err_detail:%s",
                result["err_no"],
                result["err_msg"],
                result["err_detail"],
            )
            return None, None

        return self._codec, result
