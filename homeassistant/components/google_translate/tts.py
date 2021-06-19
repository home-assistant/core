"""Support for the Google speech service."""
from io import BytesIO
import logging

from gtts import gTTS, gTTSError
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider

from . import (
    DOMAIN,
    CONF_TLD,
    CONF_SLOW,
    DEFAULT_LANG,
    SUPPORT_LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES)}
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Google speech component."""
    config = {**hass.data[DOMAIN], **config}

    return GoogleProvider(hass, config[CONF_LANG], config[CONF_TLD], config[CONF_SLOW])


class GoogleProvider(Provider):
    """The Google speech API provider."""

    def __init__(self, hass, lang, tld, slow=False):
        """Init Google TTS service."""
        self.hass = hass
        self._lang = lang
        self._tld = tld
        self._slow = slow
        self.name = "Google"

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from google."""
        tts = gTTS(
            text=message,
            tld=self._tld,
            lang=language,
            slow=self._slow,
        )
        mp3_data = BytesIO()

        try:
            tts.write_to_fp(mp3_data)
        except gTTSError as exc:
            _LOGGER.exception("Error during processing of TTS request %s", exc)
            return None, None

        return "mp3", mp3_data.getvalue()
