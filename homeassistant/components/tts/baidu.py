"""
Support for the baidu speech service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts.baidu/
"""

import logging
import voluptuous as vol

from homeassistant.const import CONF_API_KEY
from homeassistant.components.tts import Provider, PLATFORM_SCHEMA, CONF_LANG
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ["baidu-aip==2.2.8"]

_LOGGER = logging.getLogger(__name__)


SUPPORT_LANGUAGES = [
    'zh',
]
DEFAULT_LANG = 'zh'


CONF_APP_ID = 'app_id'
CONF_SECRET_KEY = 'secret_key'
CONF_SPEED = 'speed'
CONF_PITCH = 'pitch'
CONF_VOLUME = 'volume'
CONF_PERSON = 'person'

DEFAULT_SPEED = 5
DEFAULT_PITCH = 5
DEFAULT_VOLUME = 5
DEFAULT_PERSON = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
    vol.Required(CONF_APP_ID): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SECRET_KEY): cv.string,
    vol.Optional(CONF_SPEED, default=DEFAULT_SPEED): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=15)),
    vol.Optional(CONF_PITCH, default=DEFAULT_PITCH): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=15)),
    vol.Optional(CONF_VOLUME, default=DEFAULT_VOLUME): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=15)),
    vol.Optional(CONF_PERSON, default=DEFAULT_PERSON): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=4)),
})

SUPPORTED_OPTIONS = [
    CONF_SPEED,
    CONF_PITCH,
    CONF_VOLUME,
    CONF_PERSON,
]

def get_engine(hass, config):
    """Set up Baidu TTS component."""
    return BaiduTTSProvider(hass, config)


class BaiduTTSProvider(Provider):
    """Baidu TTS speech api provider."""

    def __init__(self, hass, conf):
        """Init Baidu TTS service."""
        self.hass = hass
        self._lang = conf.get(CONF_LANG)
        self._codec = 'mp3'
        self.name = 'BaiduTTS'

        self._app_data = {
            'appid': conf.get(CONF_APP_ID),
            'apikey': conf.get(CONF_API_KEY),
            'secretkey': conf.get(CONF_SECRET_KEY),
            }

        self._speech_conf_options = {
            'spd': conf.get(CONF_SPEED),
            'pit': conf.get(CONF_PITCH),
            'vol': conf.get(CONF_VOLUME),
            'per': conf.get(CONF_PERSON),
            }

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
        """Return list of supported options."""
        return SUPPORTED_OPTIONS

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from BaiduTTS."""
        from aip import AipSpeech
        aip_speech = AipSpeech(
            self._app_data['appid'],
            self._app_data['apikey'],
            self._app_data['secretkey']
            )

        if options:
            present_options = {
                'spd': options.get(CONF_SPEED, DEFAULT_SPEED),
                'pit': options.get(CONF_PITCH, DEFAULT_PITCH),
                'vol': options.get(CONF_VOLUME, DEFAULT_VOLUME),
                'per': options.get(CONF_PERSON, DEFAULT_PERSON)
                }
        else:
            present_options = self._speech_conf_options

        result = aip_speech.synthesis(
            message, language, 1, present_options)

        if isinstance(result, dict):
            _LOGGER.error(
                "Baidu TTS error-- err_no:%d; err_msg:%s; err_detail:%s",
                result['err_no'],
                result['err_msg'],
                result['err_detail'])
            return (None, None)

        return (self._codec, result)
