"""Assist satellite entity."""

from abc import abstractmethod
from collections.abc import AsyncIterable
import time
from typing import Final

from homeassistant.components import stt
from homeassistant.components.assist_pipeline import (
    OPTION_PREFERRED,
    AudioSettings,
    PipelineEvent,
    PipelineEventType,
    PipelineStage,
    async_get_pipelines,
    async_pipeline_from_audio_stream,
    vad,
)
from homeassistant.core import Context
from homeassistant.helpers import entity
from homeassistant.helpers.entity import EntityDescription
from homeassistant.util import ulid

from .models import AssistSatelliteState

_CONVERSATION_TIMEOUT_SEC: Final = 5 * 60  # 5 minutes


class AssistSatelliteEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes binary sensor entities."""


class AssistSatelliteEntity(entity.Entity):
    """Entity encapsulating the state and functionality of an Assist satellite."""

    entity_description: AssistSatelliteEntityDescription
    _attr_translation_key = "assist_satellite"
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state: AssistSatelliteState | None = None

    _conversation_id: str | None = None
    _conversation_id_time: float | None = None

    _run_has_tts: bool = False

    async def _async_accept_pipeline_from_satellite(
        self,
        audio_stream: AsyncIterable[bytes],
        start_stage: PipelineStage = PipelineStage.STT,
        end_stage: PipelineStage = PipelineStage.TTS,
        pipeline_entity_id: str | None = None,
        vad_sensitivity_entity_id: str | None = None,
        wake_word_phrase: str | None = None,
    ) -> None:
        """Triggers an Assist pipeline in Home Assistant from a satellite."""
        pipeline_id: str | None = None
        vad_sensitivity = vad.VadSensitivity.DEFAULT

        if pipeline_entity_id:
            if (
                pipeline_entity_state := self.hass.states.get(pipeline_entity_id)
            ) is None:
                raise ValueError("Pipeline entity not found")

            if pipeline_entity_state.state != OPTION_PREFERRED:
                # Resolve pipeline by name
                for pipeline in async_get_pipelines(self.hass):
                    if pipeline.name == pipeline_entity_state.state:
                        pipeline_id = pipeline.id
                        break

        if vad_sensitivity_entity_id:
            if (
                vad_sensitivity_state := self.hass.states.get(vad_sensitivity_entity_id)
            ) is None:
                raise ValueError("VAD sensitivity entity not found")

            vad_sensitivity = vad.VadSensitivity(vad_sensitivity_state.state)

        assert self.registry_entry is not None
        device_id = self.registry_entry.device_id

        # Refresh context if necessary
        if (
            (self._context is None)
            or (self._context_set is None)
            or ((time.time() - self._context_set) > entity.CONTEXT_RECENT_TIME_SECONDS)
        ):
            self.async_set_context(Context())

        assert self._context is not None

        # Reset conversation id if necessary
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
            context=self._context,
            event_callback=self._internal_on_pipeline_event,
            stt_metadata=stt.SpeechMetadata(
                language="",  # set in async_pipeline_from_audio_stream
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=audio_stream,
            pipeline_id=pipeline_id,
            conversation_id=self._conversation_id,
            device_id=device_id,
            tts_audio_output="wav",
            wake_word_phrase=wake_word_phrase,
            audio_settings=AudioSettings(
                silence_seconds=vad.VadSensitivity.to_seconds(vad_sensitivity)
            ),
            start_stage=start_stage,
            end_stage=end_stage,
        )

    @abstractmethod
    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Handle pipeline events."""

    def _internal_on_pipeline_event(self, event: PipelineEvent) -> None:
        """Set state based on pipeline stage."""
        if event.type is PipelineEventType.WAKE_WORD_START:
            self._set_state(AssistSatelliteState.LISTENING_WAKE_WORD)
        elif event.type is PipelineEventType.STT_START:
            self._set_state(AssistSatelliteState.LISTENING_COMMAND)
        elif event.type is PipelineEventType.INTENT_START:
            self._set_state(AssistSatelliteState.PROCESSING)
        elif event.type is PipelineEventType.TTS_START:
            # Wait until tts_response_finished is called to return to waiting state
            self._run_has_tts = True
            self._set_state(AssistSatelliteState.RESPONDING)
        elif event.type is PipelineEventType.RUN_END:
            if not self._run_has_tts:
                self._set_state(AssistSatelliteState.LISTENING_WAKE_WORD)

        self.on_pipeline_event(event)

    def _set_state(self, state: AssistSatelliteState):
        """Set the entity's state."""
        self._attr_state = state
        self.async_write_ha_state()

    def tts_response_finished(self) -> None:
        """Tell entity that the text-to-speech response has finished playing."""
        self._set_state(AssistSatelliteState.LISTENING_WAKE_WORD)
