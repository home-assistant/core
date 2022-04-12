"""Support for the Knovvu speech service."""
import json
import logging

import requests
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

API_URL = "https://ttsapi.knovvu.com/v1/speech/synthesis/tts"

SUPPORT_CODECS = ["mp3", "wav", "opus"]

SUPPORT_SAMPLE_RATE = [16000, 24000]

SUPPORT_VOICES = [
    "Sestek Rae 24k",
    "Sestek Sinan 24k",
    "Sestek Delal 24k",
    "Sestek Melissa 24k",
    "Sestek Gul 24k_HV_Premium",
    "Sestek Annabella 24k",
    "Sestek Darya 24k",
    "Sestek Deepti 24k",
    "Sestek Elif 24k",
    "Sestek Gladys 24k",
    "Sestek Guldestan 24k",
    "Sestek Johannes 24k",
    "Sestek Kristina 24k",
    "Sestek Marie 24k",
    "Sestek Muntaha 24k",
    "Sestek Murad 24k",
    "Sestek Oliver 24k",
    "Sestek Silas 24k",
    "Sestek Ulviye 24k",
    "Sestek Yasmin 24k",
    "Sestek Yousef 24k",
]

SUPPORT_LANGUAGES = SUPPORT_VOICES

MIN_RATE = 0.3
MAX_RATE = 3

MIN_VOLUME = 0.0
MAX_VOLUME = 2

CONF_CODEC = "codec"
CONF_VOICE = "voice"
CONF_VOLUME = "volume"
CONF_RATE = "rate"
CONF_SAMPLE_RATE = "sample_rate"

DEFAULT_CODEC = "wav"
DEFAULT_LANG = "Sestek Gul 24k_HV_Premium"
DEFAULT_VOICE = "Sestek Gul 24k_HV_Premium"
DEFAULT_VOLUME = 1
DEFAULT_RATE = 1
DEFAULT_SAMPLE_RATE = 24000

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_CODEC, default=DEFAULT_CODEC): vol.In(SUPPORT_CODECS),
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): vol.In(SUPPORT_VOICES),
        vol.Optional(CONF_SAMPLE_RATE, default=DEFAULT_SAMPLE_RATE): vol.In(
            SUPPORT_SAMPLE_RATE
        ),
        vol.Optional(CONF_RATE, default=DEFAULT_RATE): vol.Range(
            min=MIN_RATE, max=MAX_RATE
        ),
        vol.Optional(CONF_VOLUME, default=DEFAULT_VOLUME): vol.Range(
            min=MIN_VOLUME, max=MAX_VOLUME
        ),
    }
)

SUPPORTED_OPTIONS = [CONF_CODEC, CONF_VOICE, CONF_RATE, CONF_VOLUME, CONF_SAMPLE_RATE]


async def async_get_engine(hass, config, discovery_info=None):
    """Set up knovvu speech component."""
    return KnovvuProvider(hass, config)


class KnovvuProvider(Provider):
    """The knovvu speech API provider."""

    def __init__(self, hass, conf):
        """Init knovvu TTS service."""
        self.hass = hass
        self._key = conf.get(CONF_API_KEY)
        self._codec = conf.get(CONF_CODEC)
        self._language = conf.get(CONF_LANG)
        self._voice = conf.get(CONF_VOICE)
        self._volume = conf.get(CONF_VOLUME)
        self._rate = conf.get(CONF_RATE)
        self._sample_rate = conf.get(CONF_SAMPLE_RATE)
        self.name = "Knovvu"

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

    def get_tts_audio(self, message, language, options=None):
        """Request TTS file from Knovvu."""
        options = options or {}
        output_format = options.get(CONF_CODEC, self._codec)

        url = API_URL
        header = {"Authorization": self._key, "Content-Type": "application/json"}
        data_dict = {
            "Text": message,
            "Voice": {
                "Name": options.get(CONF_VOICE, self._voice),
                "Volume": options.get(CONF_VOLUME, self._volume),
                "Rate": options.get(CONF_RATE, self._rate),
            },
            "Audio": {
                "Format": output_format,
                "FormatDetails": {
                    "Encoding": "pcm",
                    "SampleRate": options.get(CONF_SAMPLE_RATE, self._sample_rate),
                },
            },
        }

        response = requests.post(
            url, headers=header, verify=False, data=json.dumps(data_dict), stream=True
        )
        audio_bytes = response.raw.read()

        return (output_format, audio_bytes)
