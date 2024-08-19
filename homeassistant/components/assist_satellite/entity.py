"""Assist satellite entity."""

from abc import abstractmethod
from collections.abc import AsyncIterable
import time
from typing import Final

from homeassistant.components import stt
from homeassistant.components.assist_pipeline import (
    AudioSettings,
    PipelineEvent,
    PipelineEventType,
    PipelineStage,
    async_pipeline_from_audio_stream,
)
from homeassistant.const import EntityCategory
from homeassistant.core import Context
from homeassistant.helpers import entity
from homeassistant.helpers.entity import EntityDescription
from homeassistant.util import ulid

from .models import AssistSatelliteState, SatelliteConfig

_CONVERSATION_TIMEOUT_SEC: Final = 5 * 60  # 5 minutes


class AssistSatelliteEntity(entity.Entity):
    """Entity encapsulating the state and functionality of an Assist satellite."""

    entity_description = EntityDescription(
        key="assist_satellite",
        translation_key="assist_satellite",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_state: AssistSatelliteState | None = (
        AssistSatelliteState.WAITING_FOR_WAKE_WORD
    )

    _satellite_config = SatelliteConfig()

    _conversation_id: str | None = None
    _conversation_id_time: float | None = None

    _run_has_tts: bool = False

    async def _async_accept_pipeline_from_satellite(
        self,
        context: Context,
        audio_stream: AsyncIterable[bytes],
        start_stage: PipelineStage = PipelineStage.STT,
        end_stage: PipelineStage = PipelineStage.TTS,
        wake_word_phrase: str | None = None,
    ) -> None:
        """Triggers an Assist pipeline in Home Assistant from a satellite."""
        device_id: str | None = None
        if self.registry_entry is not None:
            device_id = self.registry_entry.device_id

        # Reset conversation id, if necessary
        if (self._conversation_id_time is None) or (
            (time.monotonic() - self._conversation_id_time) > _CONVERSATION_TIMEOUT_SEC
        ):
            self._conversation_id = None

        if self._conversation_id is None:
            self._conversation_id = ulid.ulid()

        # Update timeout
        self._conversation_id_time = time.monotonic()

        # Set entity state based on pipeline events
        self._run_has_tts = False

        await async_pipeline_from_audio_stream(
            self.hass,
            context=context,
            event_callback=self.on_pipeline_event,
            stt_metadata=stt.SpeechMetadata(
                language="",  # set in async_pipeline_from_audio_stream
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=audio_stream,
            pipeline_id=self._satellite_config.default_pipeline,
            conversation_id=self._conversation_id,
            device_id=device_id,
            tts_audio_output="wav",
            wake_word_phrase=wake_word_phrase,
            audio_settings=AudioSettings(
                silence_seconds=self._satellite_config.finished_speaking_seconds
            ),
        )

    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Set state based on pipeline stage."""
        if event.type == PipelineEventType.WAKE_WORD_START:
            self._set_state(AssistSatelliteState.LISTENING_WAKE_WORD)
        elif event.type == PipelineEventType.STT_START:
            self._set_state(AssistSatelliteState.LISTENING_COMMAND)
        elif event.type == PipelineEventType.INTENT_START:
            self._set_state(AssistSatelliteState.PROCESSING)
        elif event.type == PipelineEventType.TTS_END:
            # Wait until tts_response_finished is called to return to idle
            self._run_has_tts = True
            self._set_state(AssistSatelliteState.RESPONDING)
        elif event.type == PipelineEventType.RUN_END:
            if not self._run_has_tts:
                self._set_state(AssistSatelliteState.WAITING_FOR_WAKE_WORD)

    async def async_get_config(self) -> SatelliteConfig:
        """Get satellite configuration."""
        return self._satellite_config

    async def async_set_config(self, config: SatelliteConfig) -> None:
        """Set satellite configuration."""
        self._satellite_config = config
        await self._async_config_updated()

    @abstractmethod
    async def _async_config_updated(self) -> None:
        """Inform when the device config is updated.

        Platforms need to make sure that the device has this configuration.
        """

    @property
    @abstractmethod
    def is_microphone_muted(self) -> bool:
        """Return if the satellite's microphone is muted."""

    def _set_state(self, state: AssistSatelliteState):
        """Set the entity's state."""
        self._attr_state = state
        self.async_write_ha_state()

    def tts_response_finished(self) -> None:
        """Tell entity that the text-to-speech response has finished playing."""
        self._set_state(AssistSatelliteState.WAITING_FOR_WAKE_WORD)
