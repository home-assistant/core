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
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.components.tts.media_source import (
    generate_media_source_id as tts_generate_media_source_id,
)
from homeassistant.core import Context
from homeassistant.helpers import entity
from homeassistant.helpers.entity import EntityDescription
from homeassistant.util import ulid

from .errors import SatelliteBusyError
from .models import AssistSatelliteEntityFeature, AssistSatelliteState

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

    _is_announcing: bool = False
    _tts_finished_event: asyncio.Event | None = None
    _wake_word_future: asyncio.Future[str | None] | None = None

    @property
    def is_announcing(self) -> bool:
        """Returns true if currently announcing."""
        return self._is_announcing

    async def async_announce(
        self,
        text: str | None = None,
        media_id: str | None = None,
    ) -> None:
        """Play an announcement on the satellite.

        If media_id is not provided, text is synthesized to
        audio with the selected pipeline.

        Calls _internal_async_announce with media id and expects it to block
        until the announcement is completed.
        """
        if text is None:
            text = ""

        if not media_id:
            # Synthesize audio and get URL
            pipeline_id = self._resolve_pipeline(pipeline_entity_id)
            pipeline = async_get_pipeline(self.hass, pipeline_id)

            tts_options: dict[str, Any] = {}
            if pipeline.tts_voice is not None:
                tts_options[tts.ATTR_VOICE] = pipeline.tts_voice

            media_id = tts_generate_media_source_id(
                self.hass,
                text,
                engine=pipeline.tts_engine,
                language=pipeline.tts_language,
                options=tts_options,
            )

        if media_source.is_media_source_id(media_id):
            media = await media_source.async_resolve_media(
                self.hass,
                media_id,
                None,
            )
            media_id = media.url

        # Resolve to full URL
        media_id = async_process_play_media_url(self.hass, media_id)

        if self._is_announcing:
            raise SatelliteBusyError

        self._is_announcing = True

        try:
            # Block until announcement is finished
            await self._internal_async_announce(media_id)
        finally:
            self._is_announcing = False

    async def _internal_async_announce(self, media_id: str) -> None:
        """Announce the media URL on the satellite and returns when finished."""
        raise NotImplementedError

    @property
    def is_intercepting_wake_word(self) -> bool:
        """Return true if next wake word will be intercepted."""
        return (self._wake_word_future is not None) and (
            not self._wake_word_future.cancelled()
        )

    async def async_intercept_wake_word(self) -> str | None:
        """Intercept the next wake word from the satellite.

        Returns the detected wake word phrase or None.
        """
        if self._wake_word_future is not None:
            raise SatelliteBusyError

        # Will cause next wake word to be intercepted in
        # _async_accept_pipeline_from_satellite
        self._wake_word_future = asyncio.Future()

        _LOGGER.debug("Next wake word will be intercepted: %s", self.entity_id)

        try:
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
        """Trigger an Assist pipeline in Home Assistant from a satellite."""
        if self.is_intercepting_wake_word:
            # Intercepting wake word and immediately end pipeline
            _LOGGER.debug(
                "Intercepted wake word: %s (entity_id=%s)",
                wake_word_phrase,
                self.entity_id,
            )
            assert self._wake_word_future is not None
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
        """Resolve pipeline from select entity to id."""
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
