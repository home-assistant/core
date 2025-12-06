"""TTS platform for the Fish Audio integration."""

from __future__ import annotations

import logging
from typing import Any

from fishaudio.exceptions import FishAudioError, RateLimitError

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FishAudioConfigEntry
from .const import (
    CONF_BACKEND,
    CONF_LATENCY,
    CONF_VOICE_ID,
    DOMAIN,
    TTS_SUPPORTED_LANGUAGES,
)

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FishAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fish Audio TTS platform."""
    _LOGGER.debug("Setting up Fish Audio TTS platform")

    _LOGGER.debug("Entry: %s", entry)
    # Iterate over values
    for subentry in entry.subentries.values():
        _LOGGER.debug("Subentry: %s", subentry)
        if subentry.subentry_type != "tts":
            continue
        async_add_entities(
            [FishAudioTTSEntity(entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class FishAudioTTSEntity(TextToSpeechEntity):
    """Fish Audio TTS entity."""

    _attr_has_entity_name = True
    _attr_supported_options = [CONF_VOICE_ID, CONF_BACKEND, CONF_LATENCY]

    def __init__(self, entry: FishAudioConfigEntry, sub_entry: ConfigSubentry) -> None:
        """Initialize the TTS entity."""
        self.client = entry.runtime_data
        self.sub_entry = sub_entry
        self._attr_unique_id = sub_entry.subentry_id
        title = sub_entry.title
        backend = sub_entry.data.get(CONF_BACKEND)
        self._attr_name = title

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sub_entry.subentry_id)},
            manufacturer="Fish Audio",
            model=backend,
            name=title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return "en"

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return TTS_SUPPORTED_LANGUAGES

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any],
    ) -> TtsAudioType:
        """Load tts audio file from engine."""

        _LOGGER.debug("Getting TTS audio for %s", message)

        voice_id = options.get(CONF_VOICE_ID, self.sub_entry.data.get(CONF_VOICE_ID))
        backend = options.get(CONF_BACKEND, self.sub_entry.data.get(CONF_BACKEND))
        latency = options.get(
            CONF_LATENCY, self.sub_entry.data.get(CONF_LATENCY, "balanced")
        )

        _LOGGER.debug("Voice ID: %s", voice_id)
        if voice_id is None:
            _LOGGER.error("Voice ID not configured")
            return None, None
        if backend is None:
            _LOGGER.error("Backend model not configured")
            return None, None

        try:
            audio = await self.client.tts.convert(
                text=message,
                reference_id=voice_id,
                latency=latency,
                model=backend,
                format="mp3",
            )
        except RateLimitError as err:
            _LOGGER.error("Fish Audio TTS rate limited: %s", err)
            raise HomeAssistantError(f"Rate limited: {err}") from err
        except FishAudioError as err:
            _LOGGER.error("Fish Audio TTS request failed: %s", err)
            raise HomeAssistantError(f"TTS request failed: {err}") from err
        except Exception:
            _LOGGER.exception("Fish Audio TTS request failed with unexpected error")
            return None, None

        return "mp3", audio
