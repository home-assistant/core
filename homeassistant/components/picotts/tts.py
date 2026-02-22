"""Support for the Pico TTS speech service."""

import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any

import voluptuous as vol

from homeassistant.components.tts import (
    CONF_LANG,
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    TextToSpeechEntity,
    TtsAudioType,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_LANG, DOMAIN, SUPPORT_LANGUAGES
from .issue import deprecate_yaml_issue

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = TTS_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES)}
)


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up Pico speech component."""
    if await hass.async_add_executor_job(shutil.which, "pico2wave") is None:
        _LOGGER.error("'pico2wave' was not found")
        return False

    if not hass.config_entries.async_entries(DOMAIN):
        _LOGGER.debug("Creating config entry by importing: %s", config)
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config
            )
        )

    deprecate_yaml_issue(hass)

    return PicoProvider(config[CONF_LANG])


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pico TTS speech component via config entry."""
    async_add_entities([PicoTTSEntity(config_entry, config_entry.data[CONF_LANG])])


class PicoTTSEntity(TextToSpeechEntity):
    """The Pico TTS API entity."""

    _attr_supported_languages = SUPPORT_LANGUAGES

    def __init__(self, config_entry: ConfigEntry, lang: str) -> None:
        """Initialize Pico TTS service."""
        self._attr_default_language = lang
        self._attr_name = f"Pico TTS {lang}"
        self._attr_unique_id = config_entry.entry_id

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS using pico2wave."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpf:
            fname = tmpf.name

        cmd = ["pico2wave", "--wave", fname, "-l", language]
        result = subprocess.run(cmd, text=True, input=message, check=False)
        data = None
        try:
            if result.returncode != 0:
                _LOGGER.error(
                    "Error running pico2wave, return code: %s", result.returncode
                )
                return None, None
            with open(fname, "rb") as voice:
                data = voice.read()
        except OSError as exc:
            _LOGGER.error("Error trying to read %s", fname)
            raise HomeAssistantError(exc) from exc
        finally:
            os.remove(fname)

        if data:
            return "wav", data
        return None, None


class PicoProvider(Provider):
    """The Pico TTS API provider."""

    def __init__(self, lang) -> None:
        """Initialize Pico TTS provider."""
        self._lang = lang
        self.name = "PicoTTS"

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS using pico2wave."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpf:
            fname = tmpf.name

        cmd = ["pico2wave", "--wave", fname, "-l", language]
        result = subprocess.run(cmd, text=True, input=message, check=False)
        data = None
        try:
            if result.returncode != 0:
                _LOGGER.error(
                    "Error running pico2wave, return code: %s", result.returncode
                )
                return None, None
            with open(fname, "rb") as voice:
                data = voice.read()
        except OSError:
            _LOGGER.error("Error trying to read %s", fname)
            return None, None
        finally:
            os.remove(fname)

        if data:
            return ("wav", data)
        return None, None
