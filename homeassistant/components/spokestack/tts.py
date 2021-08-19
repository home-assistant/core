"""Support for the Spokestack Text to Speech Service."""
import logging

from spokestack.tts.clients.spokestack import TextToSpeechClient, TTSError

from homeassistant.components.tts import CONF_LANG, Provider
from homeassistant.core import HomeAssistant

from .const import (
    CONF_IDENTITY,
    CONF_SECRET_KEY,
    DEFAULT_IDENTITY,
    DEFAULT_LANG,
    DEFAULT_MODE,
    DEFAULT_PROFILE,
    DEFAULT_SECRET_KEY,
    DEFAULT_VOICE,
    SUPPORTED_LANGUAGES,
    SUPPORTED_MODES,
    SUPPORTED_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


def get_engine(hass: HomeAssistant, config, discovery_info=None):
    """Set up Spokestack TTS provider."""
    return SpokestackProvider(hass, config)


class SpokestackProvider(Provider):
    """Spokestack TTS Provider."""

    def __init__(self, hass: HomeAssistant, config):
        """Initialize Spokestack client."""
        self._client = TextToSpeechClient(
            key_id=config.get(CONF_IDENTITY, DEFAULT_IDENTITY),
            key_secret=config.get(CONF_SECRET_KEY, DEFAULT_SECRET_KEY),
        )
        self._lang = config.get(CONF_LANG, DEFAULT_LANG)
        self._config = hass.data
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
        """Return a list of supported options like voice, emotion."""
        return SUPPORTED_OPTIONS

    @property
    def supported_modes(self):
        """Return a list of supported modes."""
        return SUPPORTED_MODES

    def get_tts_audio(self, message, language=None, options=None):
        """Convert message to speech using Spokestack API."""
        config = options or {}
        try:
            response = self._client.synthesize(
                utterance=message,
                voice=config.get("voice", DEFAULT_VOICE),
                mode=config.get("mode", DEFAULT_MODE),
                profile=config.get("profile", DEFAULT_PROFILE),
            )
        except TTSError as error:
            _LOGGER.exception("Error during processing of TTS request %s", error)
            return None, None

        audio = b""
        for data in response:
            audio += bytes(data)

        return "mp3", audio
