"""
Support for the Microsoft Cognitive Services text-to-speech service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts.microsoft/
"""
import logging
from http.client import HTTPException

import voluptuous as vol

from homeassistant.components.tts import Provider, PLATFORM_SCHEMA, CONF_LANG
from homeassistant.const import CONF_TYPE, CONF_API_KEY
import homeassistant.helpers.config_validation as cv

CONF_GENDER = 'gender'
CONF_OUTPUT = 'output'
CONF_RATE = 'rate'
CONF_VOLUME = 'volume'
CONF_PITCH = 'pitch'
CONF_CONTOUR = 'contour'

REQUIREMENTS = ["pycsspeechtts==1.0.2"]

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = [
    'ar-eg', 'ar-sa', 'ca-es', 'cs-cz', 'da-dk', 'de-at', 'de-ch', 'de-de',
    'el-gr', 'en-au', 'en-ca', 'en-gb', 'en-ie', 'en-in', 'en-us', 'es-es',
    'en-mx', 'fi-fi', 'fr-ca', 'fr-ch', 'fr-fr', 'he-il', 'hi-in', 'hu-hu',
    'id-id', 'it-it', 'ja-jp', 'ko-kr', 'nb-no', 'nl-nl', 'pl-pl', 'pt-br',
    'pt-pt', 'ro-ro', 'ru-ru', 'sk-sk', 'sv-se', 'th-th', 'tr-tr', 'zh-cn',
    'zh-hk', 'zh-tw',
]

GENDERS = [
    'Female', 'Male',
]

DEFAULT_LANG = 'en-us'
DEFAULT_GENDER = 'Female'
DEFAULT_TYPE = 'ZiraRUS'
DEFAULT_OUTPUT = 'audio-16khz-128kbitrate-mono-mp3'
DEFAULT_RATE = 0
DEFAULT_VOLUME = 0
DEFAULT_PITCH = "default"
DEFAULT_CONTOUR = ""

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
    vol.Optional(CONF_GENDER, default=DEFAULT_GENDER): vol.In(GENDERS),
    vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): cv.string,
    vol.Optional(CONF_RATE, default=DEFAULT_RATE):
        vol.All(vol.Coerce(int), vol.Range(-100, 100)),
    vol.Optional(CONF_VOLUME, default=DEFAULT_VOLUME):
        vol.All(vol.Coerce(int), vol.Range(-100, 100)),
    vol.Optional(CONF_PITCH, default=DEFAULT_PITCH): cv.string,
    vol.Optional(CONF_CONTOUR, default=DEFAULT_CONTOUR): cv.string,
})


def get_engine(hass, config):
    """Set up Microsoft speech component."""
    return MicrosoftProvider(config[CONF_API_KEY], config[CONF_LANG],
                             config[CONF_GENDER], config[CONF_TYPE],
                             config[CONF_RATE], config[CONF_VOLUME],
                             config[CONF_PITCH], config[CONF_CONTOUR])


class MicrosoftProvider(Provider):
    """The Microsoft speech API provider."""

    def __init__(self, apikey, lang, gender, ttype, rate, volume,
                 pitch, contour):
        """Init Microsoft TTS service."""
        self._apikey = apikey
        self._lang = lang
        self._gender = gender
        self._type = ttype
        self._output = DEFAULT_OUTPUT
        self._rate = "{}%".format(rate)
        self._volume = "{}%".format(volume)
        self._pitch = pitch
        self._contour = contour
        self.name = 'Microsoft'

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from Microsoft."""
        if language is None:
            language = self._lang
        from pycsspeechtts import pycsspeechtts
        try:
            trans = pycsspeechtts.TTSTranslator(self._apikey)
            data = trans.speak(language=language, gender=self._gender,
                               voiceType=self._type, output=self._output,
                               rate=self._rate, volume=self._volume,
                               pitch=self._pitch, contour=self._contour,
                               text=message)
        except HTTPException as ex:
            _LOGGER.error("Error occurred for Microsoft TTS: %s", ex)
            return(None, None)
        return ("mp3", data)
