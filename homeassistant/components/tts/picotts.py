"""
Support for the picotts speech service.
For more information see...
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

    def get_tts_audio(self, message):
        """Load TTS."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            fname = f.name
        cmd = ['pico2wave', '--wave', fname, '-l', self.language, message]
        subprocess.call(cmd)
        data = None
        try:
            with open(fname, 'rb') as voice:
                data = voice.read()
        except OSError:
            return
        finally:
            os.remove(fname)
        if data:
            return ("wav", data)
