"""Support for the Spokestack speech service."""
import logging

from spokestack.tts.clients.spokestack import TextToSpeechClient, TTSError

from homeassistant.components.tts import CONF_LANG, Provider
from homeassistant.core import HomeAssistant

from .const import (
    CONF_KEY_ID,
    CONF_KEY_SECRET,
    CONF_MODE,
    CONF_PROFILE,
    CONF_VOICE,
    DEFAULT_LANG,
    DEFAULT_MODE,
    DEFAULT_PROFILE,
    DEFAULT_VOICE,
    SUPPORTED_LANGUAGES,
    SUPPORTED_MODES,
    SUPPORTED_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


def get_engine(hass, config, discovery_info=None):
    """Set up Spokestack TTS provider."""
    return SpokestackProvider(hass)


class SpokestackProvider(Provider):
    """Spokestack TTS Provider."""

    def __init__(self, hass: HomeAssistant):
        """Initialize Spokestack client."""
        self._client = TextToSpeechClient(
            key_id=hass.data.get(CONF_KEY_ID, " "),
            key_secret=hass.data.get(CONF_KEY_SECRET, " "),
        )
        self._lang = hass.data.get(CONF_LANG, DEFAULT_LANG)
        self._mode = hass.data.get(CONF_MODE, DEFAULT_MODE)
        self._voice = hass.data.get(CONF_VOICE, DEFAULT_VOICE)
        self._profile = hass.data.get(CONF_PROFILE, DEFAULT_PROFILE)
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
        try:
            response = self._client.synthesize(
                message, voice=self._voice, mode=self._mode, profile=self._profile
            )
        except TTSError as error:
            _LOGGER.exception("Error during processing of TTS request %s", error)
            return None, None

        audio = b""
        for data in response:
            audio += bytes(data)

        return "mp3", audio
