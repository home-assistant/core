"""Assist satellite entity."""

from abc import abstractmethod
import asyncio
from collections.abc import AsyncIterable
import logging
import time
from typing import Any, Final

from homeassistant.components import media_source, stt, tts
from homeassistant.components.assist_pipeline import (
    OPTION_PREFERRED,
    AudioSettings,
    PipelineEvent,
    PipelineEventType,
    PipelineStage,
    async_get_pipeline,
    async_get_pipelines,
    async_pipeline_from_audio_stream,
    vad,
)
from homeassistant.components.tts.media_source import (
    generate_media_source_id as tts_generate_media_source_id,
)
from homeassistant.core import Context
from homeassistant.helpers import entity
from homeassistant.helpers.entity import EntityDescription
from homeassistant.util import ulid

from .errors import SatelliteBusyError
from .models import (
    AssistSatelliteEntityFeature,
    AssistSatelliteState,
    PipelineRunConfig,
)

_LOGGER = logging.getLogger(__name__)

_CONVERSATION_TIMEOUT_SEC: Final = 5 * 60  # 5 minutes


class AssistSatelliteEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes assist satellite entities."""


class AssistSatelliteEntity(entity.Entity):
    """Entity encapsulating the state and functionality of an Assist satellite."""

    entity_description: AssistSatelliteEntityDescription
    _attr_should_poll = False
    _attr_state: AssistSatelliteState | None = None
    _attr_supported_features = AssistSatelliteEntityFeature(0)

    _conversation_id: str | None = None
    _conversation_id_time: float | None = None

    _tts_finished_event: asyncio.Event | None = None
    _wake_word_future: asyncio.Future[str | None] | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._set_state(AssistSatelliteState.LISTENING_WAKE_WORD)

    async def async_trigger_pipeline_on_satellite(
        self, run_config: PipelineRunConfig
    ) -> None:
        """Run a pipeline on the satellite with the configuration.

        Requires TRIGGER_PIPELINE supported feature.
        """
        raise NotImplementedError

    async def async_announce(
        self,
        announce_text: str,
        announce_media_id: str | None = None,
        pipeline_entity_id: str | None = None,
    ) -> None:
        """Play an announcement on the satellite."""
        if self._tts_finished_event is not None:
            raise SatelliteBusyError()

        if not announce_media_id:
            # Synthesize audio and get URL
            pipeline_id = self._resolve_pipeline(pipeline_entity_id)
            pipeline = async_get_pipeline(self.hass, pipeline_id)

            tts_options: dict[str, Any] = {}
            if pipeline.tts_voice is not None:
                tts_options[tts.ATTR_VOICE] = pipeline.tts_voice

            tts_media_id = tts_generate_media_source_id(
                self.hass,
                announce_text,
                engine=pipeline.tts_engine,
                language=pipeline.tts_language,
                options=tts_options,
            )
            tts_media = await media_source.async_resolve_media(
                self.hass,
                tts_media_id,
                None,
            )
            announce_media_id = tts_media.url

        await self.async_trigger_pipeline_on_satellite(
            PipelineRunConfig(
                start_stage=PipelineStage.TTS,
                end_stage=PipelineStage.TTS,
                pipeline_entity_id=pipeline_entity_id,
                announce_text=announce_text,
                announce_media_id=announce_media_id,
            ),
        )

        # Wait for device to report that announcement has finished
        if self._tts_finished_event is not None:
            try:
                await self._tts_finished_event.wait()
            finally:
                self._tts_finished_event = None

    async def async_wait_wake(
        self,
        announce_text: str | None = None,
        announce_media_id: str | None = None,
        pipeline_entity_id: str | None = None,
    ) -> str | None:
        """Block until a wake word is detected from the satellite.

        Returns the detected wake word phrase or None.
        """
        if self._wake_word_future is not None:
            raise SatelliteBusyError()

        self._wake_word_future = asyncio.Future()

        try:
            if announce_text or announce_media_id:
                # Make announcement first
                await self.async_announce(
                    announce_text or "", announce_media_id, pipeline_entity_id
                )

            return await self._wake_word_future
        finally:
            self._wake_word_future = None

        return None

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
        if (self._wake_word_future is not None) and (
            not self._wake_word_future.cancelled()
        ):
            # Intercepting wake word
            _LOGGER.debug("Intercepted wake word: %s", wake_word_phrase)
            self._wake_word_future.set_result(wake_word_phrase)
            self._internal_on_pipeline_event(PipelineEvent(PipelineEventType.RUN_END))
            return

        pipeline_id = self._resolve_pipeline(pipeline_entity_id)

        vad_sensitivity = vad.VadSensitivity.DEFAULT
        if vad_sensitivity_entity_id:
            if (
                vad_sensitivity_state := self.hass.states.get(vad_sensitivity_entity_id)
            ) is None:
                raise ValueError("VAD sensitivity entity not found")

            vad_sensitivity = vad.VadSensitivity(vad_sensitivity_state.state)

        device_id = self.registry_entry.device_id if self.registry_entry else None

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
        self._tts_finished_event = None

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
            self._tts_finished_event = asyncio.Event()
            self._set_state(AssistSatelliteState.RESPONDING)
        elif event.type is PipelineEventType.RUN_END:
            if self._tts_finished_event is None:
                self._set_state(AssistSatelliteState.LISTENING_WAKE_WORD)

        self.on_pipeline_event(event)

    def _set_state(self, state: AssistSatelliteState):
        """Set the entity's state."""
        self._attr_state = state
        self.async_write_ha_state()

    def tts_response_finished(self) -> None:
        """Tell entity that the text-to-speech response has finished playing."""
        self._set_state(AssistSatelliteState.LISTENING_WAKE_WORD)

        if self._tts_finished_event is not None:
            self._tts_finished_event.set()

    def _resolve_pipeline(self, pipeline_entity_id: str | None) -> str | None:
        if not pipeline_entity_id:
            return None

        if (pipeline_entity_state := self.hass.states.get(pipeline_entity_id)) is None:
            raise ValueError("Pipeline entity not found")

        if pipeline_entity_state.state != OPTION_PREFERRED:
            # Resolve pipeline by name
            for pipeline in async_get_pipelines(self.hass):
                if pipeline.name == pipeline_entity_state.state:
                    return pipeline.id

        return None
