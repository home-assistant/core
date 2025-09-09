"""TTS platform for the Fish Audio integration."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

from fish_audio_sdk import Session, TTSRequest
from fish_audio_sdk.exceptions import HttpCodeErr

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FishAudioConfigEntry
from .const import CONF_BACKEND, CONF_VOICE_ID, DOMAIN, TTS_SUPPORTED_LANGUAGES
from .entity import FishAudioEntity

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FishAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fish Audio TTS platform."""
    _LOGGER.debug("Setting up Fish Audio TTS platform")
    session: Session = entry.runtime_data
    async_add_entities([FishAudioTTSEntity(entry, session)])


class FishAudioTTSEntity(FishAudioEntity, TextToSpeechEntity):
    """Fish Audio TTS entity."""

    _attr_supported_options = [CONF_VOICE_ID, CONF_BACKEND]

    def __init__(self, entry: ConfigEntry, session: Session) -> None:
        """Initialize the TTS entity."""
        super().__init__(entry, session)

        self._attr_unique_id = entry.entry_id
        self._attr_name = "Text To Speech"

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

        voice_id = options.get(CONF_VOICE_ID, self.entry.options.get(CONF_VOICE_ID))
        backend = options.get(CONF_BACKEND, self.entry.options.get(CONF_BACKEND))

        _LOGGER.debug("Voice ID: %s", voice_id)
        if voice_id is None:
            _LOGGER.error("Voice ID not configured")
            return None, None
        if backend is None:
            _LOGGER.error("Backend model not configured")
            return None, None

        request = TTSRequest(text=message, reference_id=voice_id)
        func = partial(self._session.tts, request=request, backend=backend)
        try:
            response = await self.hass.async_add_executor_job(func)
        except HttpCodeErr as err:
            if err.code == 402:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "payment_required",
                    is_fixable=False,
                    severity=ir.IssueSeverity.CRITICAL,
                    translation_key="payment_required",
                )
            _LOGGER.exception("Fish Audio TTS request failed")
            raise HomeAssistantError(str(err)) from err
        except Exception:
            _LOGGER.exception("Fish Audio TTS request failed")
            return None, None

        ir.async_delete_issue(self.hass, DOMAIN, "payment_required")
        return "mp3", b"".join(response)
