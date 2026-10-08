"""Support for the Pico TTS speech service."""

import contextlib
import logging
import os
import subprocess
import tempfile
from typing import Any, override

from homeassistant.components.tts import CONF_LANG, TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SUPPORT_LANGUAGES

_LOGGER = logging.getLogger(__name__)


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
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            model="Pico TTS",
            name=f"Pico TTS {lang}",
        )

    @override
    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS using pico2wave."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpf:
            fname = tmpf.name

        cmd = ["pico2wave", "--wave", fname, "-l", language]
        try:
            subprocess.run(cmd, text=True, input=message, check=True, timeout=30)
            with open(fname, "rb") as voice:
                data = voice.read()
        except subprocess.CalledProcessError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="returncode_error",
                translation_placeholders={"returncode": str(exc.returncode)},
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_error",
            ) from exc
        except OSError as exc:
            _LOGGER.debug("Full exception %s", exc)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="file_read_error",
                translation_placeholders={"filename": fname},
            ) from exc
        finally:
            with contextlib.suppress(OSError):
                os.remove(fname)

        return "wav", data
