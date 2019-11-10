"""Support for the Pico TTS speech service."""
import logging
import os
import shutil
import subprocess
import tempfile

import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider

_LOGGER = logging.getLogger(__name__)

SUPPORT_LANGUAGES = ["en-US", "en-GB", "de-DE", "es-ES", "fr-FR", "it-IT"]

DEFAULT_LANG = "en-US"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES)}
)


def get_engine(hass, config, discovery_info=None):
    """Set up Pico speech component."""
    if shutil.which("pico2wave") is None:
        _LOGGER.error("'pico2wave' was not found")
        return False
    return PicoProvider(config[CONF_LANG])


class PicoProvider(Provider):
    """The Pico TTS API provider."""

    def __init__(self, lang):
        """Initialize Pico TTS provider."""
        self._lang = lang
        self.name = "PicoTTS"

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    def get_tts_audio(self, message, language, options=None):
        """Load TTS using pico2wave."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpf:
            fname = tmpf.name

        cmd = ["pico2wave", "--wave", fname, "-l", language, message]
        subprocess.call(cmd)
        data = None
        try:
            with open(fname, "rb") as voice:
                data = voice.read()
        except OSError:
            _LOGGER.error("Error trying to read %s", fname)
            return (None, None)
        finally:
            os.remove(fname)

        if data:
            return ("wav", data)
        return (None, None)
