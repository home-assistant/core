"""Support for the Google speech service."""
from io import BytesIO
import logging

from gtts import gTTS, gTTSError
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider

from .const import MAP_LANG_TLD, SUPPORT_LANGUAGES, SUPPORT_TLD

_LOGGER = logging.getLogger(__name__)

DEFAULT_LANG = "en"

SUPPORT_OPTIONS = ["tld"]

DEFAULT_TLD = "com"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional("tld", default=DEFAULT_TLD): vol.In(SUPPORT_TLD),
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Google speech component."""
    return GoogleProvider(hass, config[CONF_LANG], config["tld"])


class GoogleProvider(Provider):
    """The Google speech API provider."""

    def __init__(self, hass, lang, tld):
        """Init Google TTS service."""
        self.hass = hass
        if lang in MAP_LANG_TLD:
            self._lang = MAP_LANG_TLD[lang].lang
            self._tld = MAP_LANG_TLD[lang].tld
        else:
            self._lang = lang
            self._tld = tld
        self.name = "Google"

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
        """Return a list of supported options."""
        return SUPPORT_OPTIONS

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from google."""
        tld = self._tld
        if language in MAP_LANG_TLD:
            tld = MAP_LANG_TLD[language].tld
            language = MAP_LANG_TLD[language].lang
        if options is not None and "tld" in options:
            tld = options["tld"]
        tts = gTTS(text=message, lang=language, tld=tld)
        mp3_data = BytesIO()

        try:
            tts.write_to_fp(mp3_data)
        except gTTSError as exc:
            _LOGGER.exception("Error during processing of TTS request %s", exc)
            return None, None

        return "mp3", mp3_data.getvalue()
