"""Support for the CAMB AI speech service."""

from __future__ import annotations

from io import BytesIO
import logging
from typing import Any

from camb.client import CambAI
from camb.types import StreamTtsOutputConfiguration

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_API_KEY,
    CONF_SPEECH_MODEL,
    CONF_VOICE_ID,
    DEFAULT_LANG,
    DEFAULT_SPEECH_MODEL,
    DEFAULT_VOICE_ID,
    DOMAIN,
    SUPPORT_LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_OPTIONS = ["voice_id", "speech_model"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up CAMB AI TTS platform via config entry."""
    async_add_entities([CambTTSEntity(config_entry)])


class CambTTSEntity(TextToSpeechEntity):
    """The CAMB AI TTS entity."""

    _attr_supported_languages = SUPPORT_LANGUAGES
    _attr_supported_options = SUPPORT_OPTIONS

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Init CAMB AI TTS service."""
        self._api_key: str = config_entry.data[CONF_API_KEY]
        self._voice_id: int = config_entry.data.get(CONF_VOICE_ID, DEFAULT_VOICE_ID)
        self._speech_model: str = config_entry.data.get(
            CONF_SPEECH_MODEL, DEFAULT_SPEECH_MODEL
        )
        self._attr_default_language = config_entry.data.get("language", DEFAULT_LANG)
        self._attr_name = "CAMB AI TTS"
        self._attr_unique_id = config_entry.entry_id

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="CAMB AI",
            model="MARS TTS",
        )

        self._client: CambAI | None = None

    def _get_client(self) -> CambAI:
        """Get or create CAMB AI client."""
        if self._client is None:
            self._client = CambAI(api_key=self._api_key)
        return self._client

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Load TTS from CAMB AI."""
        voice_id = self._voice_id
        speech_model = self._speech_model

        if options is not None:
            if "voice_id" in options:
                voice_id = int(options["voice_id"])
            if "speech_model" in options:
                speech_model = options["speech_model"]

        try:
            client = self._get_client()
            stream = client.text_to_speech.tts(
                text=message,
                language=language,
                voice_id=voice_id,
                speech_model=speech_model,
                output_configuration=StreamTtsOutputConfiguration(format="wav"),
            )

            audio_data = BytesIO()
            for chunk in stream:
                audio_data.write(chunk)

        except Exception as exc:
            _LOGGER.debug(
                "Error during processing of TTS request %s", exc, exc_info=True
            )
            raise HomeAssistantError(exc) from exc

        return "wav", audio_data.getvalue()
