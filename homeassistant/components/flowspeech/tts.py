"""TTS platform for the FlowSpeech integration."""

from functools import partial
from typing import Any

from flowspeech_sdk import FlowSpeechError, FlowSpeechRateLimitError

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_VOICE, DEFAULT_VOICE, DOMAIN, MANUFACTURER, SUPPORTED_LANGUAGES
from .types import FlowSpeechConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlowSpeechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FlowSpeech TTS platform."""
    async_add_entities([FlowSpeechTTSEntity(entry)])


class FlowSpeechTTSEntity(TextToSpeechEntity):
    """FlowSpeech TTS entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_options = [CONF_VOICE]

    def __init__(self, entry: FlowSpeechConfigEntry) -> None:
        """Initialize the TTS entity."""
        self.entry = entry
        self.client = entry.runtime_data
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model="Text To Speech",
            name="FlowSpeech",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return "en"

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return SUPPORTED_LANGUAGES

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any],
    ) -> TtsAudioType:
        """Load TTS audio from FlowSpeech."""
        voice = options.get(CONF_VOICE) or self.entry.data.get(CONF_VOICE) or DEFAULT_VOICE
        if not isinstance(voice, str) or not voice.strip():
            raise ServiceValidationError("FlowSpeech voice is required")

        try:
            result = await self.hass.async_add_executor_job(
                partial(self.client.synthesize, message, voice=voice)
            )
        except FlowSpeechRateLimitError as err:
            raise HomeAssistantError(f"FlowSpeech rate limited the request: {err}") from err
        except FlowSpeechError as err:
            raise HomeAssistantError(f"FlowSpeech TTS request failed: {err}") from err

        return result.audio_format, result.audio
