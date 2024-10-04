"""Assist satellite entity."""

from abc import abstractmethod
import asyncio
from collections.abc import AsyncIterable
import contextlib
from dataclasses import dataclass
from enum import StrEnum
import logging
import time
from typing import Any, Final, Literal, final

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
from homeassistant.components.tts import (
    generate_media_source_id as tts_generate_media_source_id,
)
from homeassistant.core import Context, callback
from homeassistant.helpers import entity
from homeassistant.helpers.entity import EntityDescription

from .const import AssistSatelliteEntityFeature
from .errors import AssistSatelliteError, SatelliteBusyError

_CONVERSATION_TIMEOUT_SEC: Final = 5 * 60  # 5 minutes

_LOGGER = logging.getLogger(__name__)


class AssistSatelliteState(StrEnum):
    """Valid states of an Assist satellite entity."""

    IDLE = "idle"
    """Device is waiting for user input, such as a wake word or a button press."""

    LISTENING = "listening"
    """Device is streaming audio with the voice command to Home Assistant."""

    PROCESSING = "processing"
    """Home Assistant is processing the voice command."""

    RESPONDING = "responding"
    """Device is speaking the response."""


class AssistSatelliteEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes Assist satellite entities."""


@dataclass(frozen=True)
class AssistSatelliteWakeWord:
    """Available wake word model."""

    id: str
    """Unique id for wake word model."""

    wake_word: str
    """Wake word phrase."""

    trained_languages: list[str]
    """List of languages that the wake word was trained on."""


@dataclass
class AssistSatelliteConfiguration:
    """Satellite configuration."""

    available_wake_words: list[AssistSatelliteWakeWord]
    """List of available available wake word models."""

    active_wake_words: list[str]
    """List of active wake word ids."""

    max_active_wake_words: int
    """Maximum number of simultaneous wake words allowed (0 for no limit)."""


@dataclass
class AssistSatelliteAnnouncement:
    """Announcement to be made."""

    message: str
    """Message to be spoken."""

    media_id: str
    """Media ID to be played."""

    media_id_source: Literal["url", "media_id", "tts"]


class AssistSatelliteEntity(entity.Entity):
    """Entity encapsulating the state and functionality of an Assist satellite."""

    entity_description: AssistSatelliteEntityDescription
    _attr_should_poll = False
    _attr_supported_features = AssistSatelliteEntityFeature(0)
    _attr_pipeline_entity_id: str | None = None
    _attr_vad_sensitivity_entity_id: str | None = None

    _conversation_id: str | None = None
    _conversation_id_time: float | None = None

    _run_has_tts: bool = False
    _is_announcing = False
    _wake_word_intercept_future: asyncio.Future[str | None] | None = None
    _attr_tts_options: dict[str, Any] | None = None
    _pipeline_task: asyncio.Task | None = None

    __assist_satellite_state = AssistSatelliteState.IDLE

    @final
    @property
    def state(self) -> str | None:
        """Return state of the entity."""
        return self.__assist_satellite_state

    @property
    def pipeline_entity_id(self) -> str | None:
        """Entity ID of the pipeline to use for the next conversation."""
        return self._attr_pipeline_entity_id

    @property
    def vad_sensitivity_entity_id(self) -> str | None:
        """Entity ID of the VAD sensitivity to use for the next conversation."""
        return self._attr_vad_sensitivity_entity_id

    @property
    def tts_options(self) -> dict[str, Any] | None:
        """Options passed for text-to-speech."""
        return self._attr_tts_options

    @callback
    @abstractmethod
    def async_get_configuration(self) -> AssistSatelliteConfiguration:
        """Get the current satellite configuration."""

    @abstractmethod
    async def async_set_configuration(
        self, config: AssistSatelliteConfiguration
    ) -> None:
        """Set the current satellite configuration."""

    async def async_intercept_wake_word(self) -> str | None:
        """Intercept the next wake word from the satellite.

        Returns the detected wake word phrase or None.
        """
        if self._wake_word_intercept_future is not None:
            raise SatelliteBusyError("Wake word interception already in progress")

        # Will cause next wake word to be intercepted in
        # async_accept_pipeline_from_satellite
        self._wake_word_intercept_future = asyncio.Future()

        _LOGGER.debug("Next wake word will be intercepted: %s", self.entity_id)

        try:
            return await self._wake_word_intercept_future
        finally:
            self._wake_word_intercept_future = None

    async def async_internal_announce(
        self,
        message: str | None = None,
        media_id: str | None = None,
    ) -> None:
        """Play and show an announcement on the satellite.

        If media_id is not provided, message is synthesized to
        audio with the selected pipeline.

        If media_id is provided, it is played directly. It is possible
        to omit the message and the satellite will not show any text.

        Calls async_announce with message and media id.
        """
        await self._cancel_running_pipeline()

        media_id_source: Literal["url", "media_id", "tts"] | None = None

        if message is None:
            message = ""

        if not media_id:
            media_id_source = "tts"
            # Synthesize audio and get URL
            pipeline_id = self._resolve_pipeline()
            pipeline = async_get_pipeline(self.hass, pipeline_id)

            tts_options: dict[str, Any] = {}
            if pipeline.tts_voice is not None:
                tts_options[tts.ATTR_VOICE] = pipeline.tts_voice

            if self.tts_options is not None:
                tts_options.update(self.tts_options)

            media_id = tts_generate_media_source_id(
                self.hass,
                message,
                engine=pipeline.tts_engine,
                language=pipeline.tts_language,
                options=tts_options,
            )

        if media_source.is_media_source_id(media_id):
            if not media_id_source:
                media_id_source = "media_id"
            media = await media_source.async_resolve_media(
                self.hass,
                media_id,
                None,
            )
            media_id = media.url

        if not media_id_source:
            media_id_source = "url"

        # Resolve to full URL
        media_id = async_process_play_media_url(self.hass, media_id)

        if self._is_announcing:
            raise SatelliteBusyError

        self._is_announcing = True
        self._set_state(AssistSatelliteState.RESPONDING)

        try:
            # Block until announcement is finished
            await self.async_announce(
                AssistSatelliteAnnouncement(message, media_id, media_id_source)
            )
        finally:
            self._is_announcing = False
            self._set_state(AssistSatelliteState.IDLE)

    async def async_announce(self, announcement: AssistSatelliteAnnouncement) -> None:
        """Announce media on the satellite.

        Should block until the announcement is done playing.
        """
        raise NotImplementedError

    async def async_accept_pipeline_from_satellite(
        self,
        audio_stream: AsyncIterable[bytes],
        start_stage: PipelineStage = PipelineStage.STT,
        end_stage: PipelineStage = PipelineStage.TTS,
        wake_word_phrase: str | None = None,
    ) -> None:
        """Triggers an Assist pipeline in Home Assistant from a satellite."""
        await self._cancel_running_pipeline()

        if self._wake_word_intercept_future and start_stage in (
            PipelineStage.WAKE_WORD,
            PipelineStage.STT,
        ):
            if start_stage == PipelineStage.WAKE_WORD:
                self._wake_word_intercept_future.set_exception(
                    AssistSatelliteError(
                        "Only on-device wake words currently supported"
                    )
                )
                return

            # Intercepting wake word and immediately end pipeline
            _LOGGER.debug(
                "Intercepted wake word: %s (entity_id=%s)",
                wake_word_phrase,
                self.entity_id,
            )

            if wake_word_phrase is None:
                self._wake_word_intercept_future.set_exception(
                    AssistSatelliteError("No wake word phrase provided")
                )
            else:
                self._wake_word_intercept_future.set_result(wake_word_phrase)
            self._internal_on_pipeline_event(PipelineEvent(PipelineEventType.RUN_END))
            return

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
        if self._conversation_id_time and (
            (time.monotonic() - self._conversation_id_time) > _CONVERSATION_TIMEOUT_SEC
        ):
            self._conversation_id = None
            self._conversation_id_time = None

        # Set entity state based on pipeline events
        self._run_has_tts = False

        assert self.platform.config_entry is not None
        self._pipeline_task = self.platform.config_entry.async_create_background_task(
            self.hass,
            async_pipeline_from_audio_stream(
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
                pipeline_id=self._resolve_pipeline(),
                conversation_id=self._conversation_id,
                device_id=device_id,
                tts_audio_output=self.tts_options,
                wake_word_phrase=wake_word_phrase,
                audio_settings=AudioSettings(
                    silence_seconds=self._resolve_vad_sensitivity()
                ),
                start_stage=start_stage,
                end_stage=end_stage,
            ),
            f"{self.entity_id}_pipeline",
        )

        try:
            await self._pipeline_task
        finally:
            self._pipeline_task = None

    async def _cancel_running_pipeline(self) -> None:
        """Cancel the current pipeline if it's running."""
        if self._pipeline_task is not None:
            self._pipeline_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pipeline_task

            self._pipeline_task = None

    @abstractmethod
    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Handle pipeline events."""

    @callback
    def _internal_on_pipeline_event(self, event: PipelineEvent) -> None:
        """Set state based on pipeline stage."""
        if event.type is PipelineEventType.WAKE_WORD_START:
            self._set_state(AssistSatelliteState.IDLE)
        elif event.type is PipelineEventType.STT_START:
            self._set_state(AssistSatelliteState.LISTENING)
        elif event.type is PipelineEventType.INTENT_START:
            self._set_state(AssistSatelliteState.PROCESSING)
        elif event.type is PipelineEventType.INTENT_END:
            assert event.data is not None
            # Update timeout
            self._conversation_id_time = time.monotonic()
            self._conversation_id = event.data["intent_output"]["conversation_id"]
        elif event.type is PipelineEventType.TTS_START:
            # Wait until tts_response_finished is called to return to waiting state
            self._run_has_tts = True
            self._set_state(AssistSatelliteState.RESPONDING)
        elif event.type is PipelineEventType.RUN_END:
            if not self._run_has_tts:
                self._set_state(AssistSatelliteState.IDLE)

        self.on_pipeline_event(event)

    @callback
    def _set_state(self, state: AssistSatelliteState) -> None:
        """Set the entity's state."""
        self.__assist_satellite_state = state
        self.async_write_ha_state()

    @callback
    def tts_response_finished(self) -> None:
        """Tell entity that the text-to-speech response has finished playing."""
        self._set_state(AssistSatelliteState.IDLE)

    @callback
    def _resolve_pipeline(self) -> str | None:
        """Resolve pipeline from select entity to id.

        Return None to make async_get_pipeline look up the preferred pipeline.
        """
        if not (pipeline_entity_id := self.pipeline_entity_id):
            return None

        if (pipeline_entity_state := self.hass.states.get(pipeline_entity_id)) is None:
            raise RuntimeError("Pipeline entity not found")

        if pipeline_entity_state.state != OPTION_PREFERRED:
            # Resolve pipeline by name
            for pipeline in async_get_pipelines(self.hass):
                if pipeline.name == pipeline_entity_state.state:
                    return pipeline.id

        return None

    @callback
    def _resolve_vad_sensitivity(self) -> float:
        """Resolve VAD sensitivity from select entity to enum."""
        vad_sensitivity = vad.VadSensitivity.DEFAULT

        if vad_sensitivity_entity_id := self.vad_sensitivity_entity_id:
            if (
                vad_sensitivity_state := self.hass.states.get(vad_sensitivity_entity_id)
            ) is None:
                raise RuntimeError("VAD sensitivity entity not found")

            vad_sensitivity = vad.VadSensitivity(vad_sensitivity_state.state)

        return vad.VadSensitivity.to_seconds(vad_sensitivity)
