"""
Support for the picotts speech service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts/picotts/
"""
import os
import tempfile
import shutil
import subprocess
import logging
import voluptuous as vol

from homeassistant.components.tts import Provider, PLATFORM_SCHEMA, CONF_LANG

_LOGGER = logging.getLogger(__name__)

SUPPORT_LANGUAGES = ['en-US', 'en-GB', 'de-DE', 'es-ES', 'fr-FR', 'it-IT']

DEFAULT_LANG = 'en-US'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
})


def get_engine(hass, config):
    """Setup pico speech component."""
    if shutil.which("pico2wave") is None:
        _LOGGER.error("'pico2wave' was not found")
        return False
    return PicoProvider()


class PicoProvider(Provider):
    """pico speech api provider."""

    def get_tts_audio(self, message, language=None):
        """Load TTS using pico2wave."""
        if language not in SUPPORT_LANGUAGES:
            language = self.language
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpf:
            fname = tmpf.name
        cmd = ['pico2wave', '--wave', fname, '-l', language, message]
        subprocess.call(cmd)
        data = None
        try:
            with open(fname, 'rb') as voice:
                data = voice.read()
        except OSError:
            _LOGGER.error("Error trying to read %s", fname)
            return (None, None)
        finally:
            os.remove(fname)
        if data:
            return ("wav", data)
        return (None, None)
