"""Support for the Spokestack speech service."""
import logging

from spokestack.tts.clients.spokestack import TextToSpeechClient, TTSError
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_KEY_ID,
    CONF_MODE,
    CONF_SECRET_KEY,
    CONF_VOICE,
    DEFAULT_LANG,
    DEFAULT_MODE,
    DEFAULT_VOICE,
    SUPPORTED_LANGUAGES,
    SUPPORTED_MODES,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_KEY): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(SUPPORTED_MODES),
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): cv.string,
    }
)


def get_engine(hass, config, discovery_info=None):
    """Set up Spokestack TTS provider."""
    return SpokestackProvider(hass, config)


class SpokestackProvider(Provider):
    """Spokestack TTS Provider."""

    def __init__(self, hass, config):
        """Initialize Spokestack client."""
        self._client = TextToSpeechClient(config[CONF_KEY_ID], config[CONF_SECRET_KEY])
        self._lang = config[CONF_LANG]
        self._config = config
        self.name = "Spokestack"

    @property
    def default_language(self):
        """Return the default language."""
        return DEFAULT_LANG

    @property
    def supported_languages(self):
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_options(self):
        """Return a list of supported options like voice, emotionen."""
        return ["voice", "mode"]

    def get_tts_audio(self, message, language=None, options=None):
        """Convert message to speech using Spokestack API."""

        try:
            response = self._client.synthesize(
                message,
                self._config[CONF_VOICE],
                self._config[CONF_MODE],
            )
        except TTSError as error:
            _LOGGER.exception("Error during processing of TTS request %s", error)
            return None, None

        audio = b""
        for data in response:
            audio += data

        return "mp3", audio
