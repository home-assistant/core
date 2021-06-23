"""Support for the AIS TTS Local speech service."""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider

_LOGGER = logging.getLogger(__name__)

SUPPORT_LANGUAGES = ["pl_PL", "en_US", "en_GB", "de_DE", "es_ES", "fr_FR"]

DEFAULT_LANG = "pl_PL"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES)}
)


def get_engine(hass, config, discovery_info=None):
    """Set up AIS speech component."""
    return AisTtsLocalProvider(config[CONF_LANG], hass)


class AisTtsLocalProvider(Provider):
    """The AIS TTS API provider."""

    def __init__(self, lang, hass):
        """Initialize AIS TTS Local provider."""
        self._lang = lang
        self.name = "AisTtsLocal"
        self.hass = hass

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    async def async_get_tts_audio(self, message, language, options=None):
        """Load AIS TTS Local using."""
        temp_file_name = "/data/data/pl.sviete.dom/files/home/AIS/www/temp.wav"

        await self.hass.services.async_call(
            "ais_ai_service",
            "say_it",
            {"text": message, "language": language, "path": temp_file_name},
        )
        # wait for the file
        data = None
        check = 0
        while check < 3:
            await asyncio.sleep(1)
            if os.path.isfile(temp_file_name):
                try:
                    with open(temp_file_name, "rb") as voice:
                        data = voice.read()
                except OSError:
                    _LOGGER.error("Error trying to read %s", temp_file_name)
                    return None, None
                finally:
                    os.remove(temp_file_name)
                check = 3
            check = check + 1

        if data:
            return "wav", data
        return None, None
