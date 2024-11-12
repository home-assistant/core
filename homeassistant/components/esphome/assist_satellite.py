"""Support for assist satellites in ESPHome."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from functools import partial
import io
from itertools import chain
import logging
import socket
from typing import Any, cast
import wave

from aioesphomeapi import (
    MediaPlayerFormatPurpose,
    MediaPlayerSupportedFormat,
    VoiceAssistantAnnounceFinished,
    VoiceAssistantAudioSettings,
    VoiceAssistantCommandFlag,
    VoiceAssistantEventType,
    VoiceAssistantFeature,
    VoiceAssistantTimerEventType,
)

from homeassistant.components import assist_satellite, tts
from homeassistant.components.assist_pipeline import (
    PipelineEvent,
    PipelineEventType,
    PipelineStage,
)
from homeassistant.components.intent import (
    TimerEventType,
    TimerInfo,
    async_register_timer_handler,
)
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EsphomeAssistEntity
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData
from .enum_mapper import EsphomeEnumMapper
from .ffmpeg_proxy import async_create_proxy_url

_LOGGER = logging.getLogger(__name__)

_VOICE_ASSISTANT_EVENT_TYPES: EsphomeEnumMapper[
    VoiceAssistantEventType, PipelineEventType
] = EsphomeEnumMapper(
    {
        VoiceAssistantEventType.VOICE_ASSISTANT_ERROR: PipelineEventType.ERROR,
        VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START: PipelineEventType.RUN_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_RUN_END: PipelineEventType.RUN_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_STT_START: PipelineEventType.STT_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_STT_END: PipelineEventType.STT_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_START: PipelineEventType.INTENT_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_END: PipelineEventType.INTENT_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_TTS_START: PipelineEventType.TTS_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END: PipelineEventType.TTS_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_WAKE_WORD_START: PipelineEventType.WAKE_WORD_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_WAKE_WORD_END: PipelineEventType.WAKE_WORD_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_STT_VAD_START: PipelineEventType.STT_VAD_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_STT_VAD_END: PipelineEventType.STT_VAD_END,
    }
)

_TIMER_EVENT_TYPES: EsphomeEnumMapper[VoiceAssistantTimerEventType, TimerEventType] = (
    EsphomeEnumMapper(
        {
            VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_STARTED: TimerEventType.STARTED,
            VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_UPDATED: TimerEventType.UPDATED,
            VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_CANCELLED: TimerEventType.CANCELLED,
            VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_FINISHED: TimerEventType.FINISHED,
        }
    )
)

_ANNOUNCEMENT_TIMEOUT_SEC = 5 * 60  # 5 minutes
_CONFIG_TIMEOUT_SEC = 5


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Assist satellite entity."""
    entry_data = entry.runtime_data
    assert entry_data.device_info is not None
    if entry_data.device_info.voice_assistant_feature_flags_compat(
        entry_data.api_version
    ):
        async_add_entities(
            [
                EsphomeAssistSatellite(entry, entry_data),
            ]
        )


class EsphomeAssistSatellite(
    EsphomeAssistEntity, assist_satellite.AssistSatelliteEntity
):
    """Satellite running ESPHome."""

    entity_description = assist_satellite.AssistSatelliteEntityDescription(
        key="assist_satellite", translation_key="assist_satellite"
    )

    def __init__(
        self,
        config_entry: ConfigEntry,
        entry_data: RuntimeEntryData,
    ) -> None:
        """Initialize satellite."""
        super().__init__(entry_data)

        self.config_entry = config_entry
        self.entry_data = entry_data
        self.cli = self.entry_data.client

        self._is_running: bool = True
        self._pipeline_task: asyncio.Task | None = None
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._tts_streaming_task: asyncio.Task | None = None
        self._udp_server: VoiceAssistantUDPServer | None = None

        # Empty config. Updated when added to HA.
        self._satellite_config = assist_satellite.AssistSatelliteConfiguration(
            available_wake_words=[], active_wake_words=[], max_active_wake_words=1
        )

    @property
    def pipeline_entity_id(self) -> str | None:
        """Return the entity ID of the pipeline to use for the next conversation."""
        assert self.entry_data.device_info is not None
        ent_reg = er.async_get(self.hass)
        return ent_reg.async_get_entity_id(
            Platform.SELECT,
            DOMAIN,
            f"{self.entry_data.device_info.mac_address}-pipeline",
        )

    @property
    def vad_sensitivity_entity_id(self) -> str | None:
        """Return the entity ID of the VAD sensitivity to use for the next conversation."""
        assert self.entry_data.device_info is not None
        ent_reg = er.async_get(self.hass)
        return ent_reg.async_get_entity_id(
            Platform.SELECT,
            DOMAIN,
            f"{self.entry_data.device_info.mac_address}-vad_sensitivity",
        )

    @callback
    def async_get_configuration(
        self,
    ) -> assist_satellite.AssistSatelliteConfiguration:
        """Get the current satellite configuration."""
        return self._satellite_config

    async def async_set_configuration(
        self, config: assist_satellite.AssistSatelliteConfiguration
    ) -> None:
        """Set the current satellite configuration."""
        await self.cli.set_voice_assistant_configuration(
            active_wake_words=config.active_wake_words
        )
        _LOGGER.debug("Set active wake words: %s", config.active_wake_words)

        # Ensure configuration is updated
        await self._update_satellite_config()

    async def _update_satellite_config(self) -> None:
        """Get the latest satellite configuration from the device."""
        try:
            config = await self.cli.get_voice_assistant_configuration(
                _CONFIG_TIMEOUT_SEC
            )
        except TimeoutError:
            # Placeholder config will be used
            return

        # Update available/active wake words
        self._satellite_config.available_wake_words = [
            assist_satellite.AssistSatelliteWakeWord(
                id=model.id,
                wake_word=model.wake_word,
                trained_languages=list(model.trained_languages),
            )
            for model in config.available_wake_words
        ]
        self._satellite_config.active_wake_words = list(config.active_wake_words)
        self._satellite_config.max_active_wake_words = config.max_active_wake_words
        _LOGGER.debug("Received satellite configuration: %s", self._satellite_config)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        assert self.entry_data.device_info is not None
        feature_flags = (
            self.entry_data.device_info.voice_assistant_feature_flags_compat(
                self.entry_data.api_version
            )
        )
        if feature_flags & VoiceAssistantFeature.API_AUDIO:
            # TCP audio
            self.async_on_remove(
                self.cli.subscribe_voice_assistant(
                    handle_start=self.handle_pipeline_start,
                    handle_stop=self.handle_pipeline_stop,
                    handle_audio=self.handle_audio,
                    handle_announcement_finished=self.handle_announcement_finished,
                )
            )
        else:
            # UDP audio
            self.async_on_remove(
                self.cli.subscribe_voice_assistant(
                    handle_start=self.handle_pipeline_start,
                    handle_stop=self.handle_pipeline_stop,
                    handle_announcement_finished=self.handle_announcement_finished,
                )
            )

        if feature_flags & VoiceAssistantFeature.TIMERS:
            # Device supports timers
            assert (self.registry_entry is not None) and (
                self.registry_entry.device_id is not None
            )
            self.async_on_remove(
                async_register_timer_handler(
                    self.hass, self.registry_entry.device_id, self.handle_timer_event
                )
            )

        if feature_flags & VoiceAssistantFeature.ANNOUNCE:
            # Device supports announcements
            self._attr_supported_features |= (
                assist_satellite.AssistSatelliteEntityFeature.ANNOUNCE
            )

            # Block until config is retrieved.
            # If the device supports announcements, it will return a config.
            _LOGGER.debug("Waiting for satellite configuration")
            await self._update_satellite_config()

        if not (feature_flags & VoiceAssistantFeature.SPEAKER):
            # Will use media player for TTS/announcements
            self._update_tts_format()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()

        self._is_running = False
        self._stop_pipeline()

    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Handle pipeline events."""
        try:
            event_type = _VOICE_ASSISTANT_EVENT_TYPES.from_hass(event.type)
        except KeyError:
            _LOGGER.debug("Received unknown pipeline event type: %s", event.type)
            return

        data_to_send: dict[str, Any] = {}
        if event_type == VoiceAssistantEventType.VOICE_ASSISTANT_STT_START:
            self.entry_data.async_set_assist_pipeline_state(True)
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_STT_END:
            assert event.data is not None
            data_to_send = {"text": event.data["stt_output"]["text"]}
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_END:
            assert event.data is not None
            data_to_send = {
                "conversation_id": event.data["intent_output"]["conversation_id"] or "",
            }
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_START:
            assert event.data is not None
            data_to_send = {"text": event.data["tts_input"]}
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END:
            assert event.data is not None
            if tts_output := event.data["tts_output"]:
                path = tts_output["url"]
                url = async_process_play_media_url(self.hass, path)
                data_to_send = {"url": url}

                assert self.entry_data.device_info is not None
                feature_flags = (
                    self.entry_data.device_info.voice_assistant_feature_flags_compat(
                        self.entry_data.api_version
                    )
                )
                if feature_flags & VoiceAssistantFeature.SPEAKER:
                    media_id = tts_output["media_id"]
                    self._tts_streaming_task = (
                        self.config_entry.async_create_background_task(
                            self.hass,
                            self._stream_tts_audio(media_id),
                            "esphome_voice_assistant_tts",
                        )
                    )
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_WAKE_WORD_END:
            assert event.data is not None
            if not event.data["wake_word_output"]:
                event_type = VoiceAssistantEventType.VOICE_ASSISTANT_ERROR
                data_to_send = {
                    "code": "no_wake_word",
                    "message": "No wake word detected",
                }
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_ERROR:
            assert event.data is not None
            data_to_send = {
                "code": event.data["code"],
                "message": event.data["message"],
            }
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_RUN_END:
            if self._tts_streaming_task is None:
                # No TTS
                self.entry_data.async_set_assist_pipeline_state(False)

        self.cli.send_voice_assistant_event(event_type, data_to_send)

    async def async_announce(
        self, announcement: assist_satellite.AssistSatelliteAnnouncement
    ) -> None:
        """Announce media on the satellite.

        Should block until the announcement is done playing.
        """
        _LOGGER.debug(
            "Waiting for announcement to finished (message=%s, media_id=%s)",
            announcement.message,
            announcement.media_id,
        )
        media_id = announcement.media_id
        if announcement.media_id_source != "tts":
            # Route non-TTS media through the proxy
            format_to_use: MediaPlayerSupportedFormat | None = None
            for supported_format in chain(
                *self.entry_data.media_player_formats.values()
            ):
                if supported_format.purpose == MediaPlayerFormatPurpose.ANNOUNCEMENT:
                    format_to_use = supported_format
                    break

            if format_to_use is not None:
                assert (self.registry_entry is not None) and (
                    self.registry_entry.device_id is not None
                )
                proxy_url = async_create_proxy_url(
                    self.hass,
                    self.registry_entry.device_id,
                    media_id,
                    media_format=format_to_use.format,
                    rate=format_to_use.sample_rate or None,
                    channels=format_to_use.num_channels or None,
                    width=format_to_use.sample_bytes or None,
                )
                media_id = async_process_play_media_url(self.hass, proxy_url)

        await self.cli.send_voice_assistant_announcement_await_response(
            media_id, _ANNOUNCEMENT_TIMEOUT_SEC, announcement.message
        )

    async def handle_pipeline_start(
        self,
        conversation_id: str,
        flags: int,
        audio_settings: VoiceAssistantAudioSettings,
        wake_word_phrase: str | None,
    ) -> int | None:
        """Handle pipeline run request."""
        # Clear audio queue
        while not self._audio_queue.empty():
            await self._audio_queue.get()

        if self._tts_streaming_task is not None:
            # Cancel current TTS response
            self._tts_streaming_task.cancel()
            self._tts_streaming_task = None

        # API or UDP output audio
        port: int = 0
        assert self.entry_data.device_info is not None
        feature_flags = (
            self.entry_data.device_info.voice_assistant_feature_flags_compat(
                self.entry_data.api_version
            )
        )
        if (feature_flags & VoiceAssistantFeature.SPEAKER) and not (
            feature_flags & VoiceAssistantFeature.API_AUDIO
        ):
            port = await self._start_udp_server()
            _LOGGER.debug("Started UDP server on port %s", port)

        # Device triggered pipeline (wake word, etc.)
        if flags & VoiceAssistantCommandFlag.USE_WAKE_WORD:
            start_stage = PipelineStage.WAKE_WORD
        else:
            start_stage = PipelineStage.STT

        end_stage = PipelineStage.TTS

        if feature_flags & VoiceAssistantFeature.SPEAKER:
            # Stream WAV audio
            self._attr_tts_options = {
                tts.ATTR_PREFERRED_FORMAT: "wav",
                tts.ATTR_PREFERRED_SAMPLE_RATE: 16000,
                tts.ATTR_PREFERRED_SAMPLE_CHANNELS: 1,
                tts.ATTR_PREFERRED_SAMPLE_BYTES: 2,
            }
        else:
            # ANNOUNCEMENT format from media player
            self._update_tts_format()

        # Run the pipeline
        _LOGGER.debug("Running pipeline from %s to %s", start_stage, end_stage)
        self._pipeline_task = self.config_entry.async_create_background_task(
            self.hass,
            self.async_accept_pipeline_from_satellite(
                audio_stream=self._wrap_audio_stream(),
                start_stage=start_stage,
                end_stage=end_stage,
                wake_word_phrase=wake_word_phrase,
            ),
            "esphome_assist_satellite_pipeline",
        )
        self._pipeline_task.add_done_callback(
            lambda _future: self.handle_pipeline_finished()
        )

        return port

    async def handle_audio(self, data: bytes) -> None:
        """Handle incoming audio chunk from API."""
        self._audio_queue.put_nowait(data)

    async def handle_pipeline_stop(self, abort: bool) -> None:
        """Handle request for pipeline to stop."""
        if abort:
            self._abort_pipeline()
        else:
            self._stop_pipeline()

    def handle_pipeline_finished(self) -> None:
        """Handle when pipeline has finished running."""
        self._stop_udp_server()
        _LOGGER.debug("Pipeline finished")

    def handle_timer_event(
        self, event_type: TimerEventType, timer_info: TimerInfo
    ) -> None:
        """Handle timer events."""
        try:
            native_event_type = _TIMER_EVENT_TYPES.from_hass(event_type)
        except KeyError:
            _LOGGER.debug("Received unknown timer event type: %s", event_type)
            return

        self.cli.send_voice_assistant_timer_event(
            native_event_type,
            timer_info.id,
            timer_info.name,
            timer_info.created_seconds,
            timer_info.seconds_left,
            timer_info.is_active,
        )

    async def handle_announcement_finished(
        self, announce_finished: VoiceAssistantAnnounceFinished
    ) -> None:
        """Handle announcement finished message (also sent for TTS)."""
        self.tts_response_finished()

    def _update_tts_format(self) -> None:
        """Update the TTS format from the first media player."""
        for supported_format in chain(*self.entry_data.media_player_formats.values()):
            # Find first announcement format
            if supported_format.purpose == MediaPlayerFormatPurpose.ANNOUNCEMENT:
                self._attr_tts_options = {
                    tts.ATTR_PREFERRED_FORMAT: supported_format.format,
                }

                if supported_format.sample_rate > 0:
                    self._attr_tts_options[tts.ATTR_PREFERRED_SAMPLE_RATE] = (
                        supported_format.sample_rate
                    )

                if supported_format.sample_rate > 0:
                    self._attr_tts_options[tts.ATTR_PREFERRED_SAMPLE_CHANNELS] = (
                        supported_format.num_channels
                    )

                if supported_format.sample_rate > 0:
                    self._attr_tts_options[tts.ATTR_PREFERRED_SAMPLE_BYTES] = (
                        supported_format.sample_bytes
                    )

                break

    async def _stream_tts_audio(
        self,
        media_id: str,
        sample_rate: int = 16000,
        sample_width: int = 2,
        sample_channels: int = 1,
        samples_per_chunk: int = 512,
    ) -> None:
        """Stream TTS audio chunks to device via API or UDP."""
        self.cli.send_voice_assistant_event(
            VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_START, {}
        )

        try:
            if not self._is_running:
                return

            extension, data = await tts.async_get_media_source_audio(
                self.hass,
                media_id,
            )

            if extension != "wav":
                _LOGGER.error("Only WAV audio can be streamed, got %s", extension)
                return

            with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
                if (
                    (wav_file.getframerate() != sample_rate)
                    or (wav_file.getsampwidth() != sample_width)
                    or (wav_file.getnchannels() != sample_channels)
                ):
                    _LOGGER.error("Can only stream 16Khz 16-bit mono WAV")
                    return

                _LOGGER.debug("Streaming %s audio samples", wav_file.getnframes())

                while self._is_running:
                    chunk = wav_file.readframes(samples_per_chunk)
                    if not chunk:
                        break

                    if self._udp_server is not None:
                        self._udp_server.send_audio_bytes(chunk)
                    else:
                        self.cli.send_voice_assistant_audio(chunk)

                    # Wait for 90% of the duration of the audio that was
                    # sent for it to be played.  This will overrun the
                    # device's buffer for very long audio, so using a media
                    # player is preferred.
                    samples_in_chunk = len(chunk) // (sample_width * sample_channels)
                    seconds_in_chunk = samples_in_chunk / sample_rate
                    await asyncio.sleep(seconds_in_chunk * 0.9)
        except asyncio.CancelledError:
            return  # Don't trigger state change
        finally:
            self.cli.send_voice_assistant_event(
                VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_END, {}
            )

        # State change
        self.tts_response_finished()
        self.entry_data.async_set_assist_pipeline_state(False)

    async def _wrap_audio_stream(self) -> AsyncIterable[bytes]:
        """Yield audio chunks from the queue until None."""
        while True:
            chunk = await self._audio_queue.get()
            if not chunk:
                break

            yield chunk

    def _stop_pipeline(self) -> None:
        """Request pipeline to be stopped by ending the audio stream and continue processing."""
        self._audio_queue.put_nowait(None)
        _LOGGER.debug("Requested pipeline stop")

    def _abort_pipeline(self) -> None:
        """Request pipeline to be aborted (no further processing)."""
        _LOGGER.debug("Requested pipeline abort")
        self._audio_queue.put_nowait(None)
        if self._pipeline_task is not None:
            self._pipeline_task.cancel()

    async def _start_udp_server(self) -> int:
        """Start a UDP server on a random free port."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.bind(("", 0))  # random free port

        (
            _transport,
            protocol,
        ) = await asyncio.get_running_loop().create_datagram_endpoint(
            partial(VoiceAssistantUDPServer, self._audio_queue), sock=sock
        )

        assert isinstance(protocol, VoiceAssistantUDPServer)
        self._udp_server = protocol

        # Return port
        return cast(int, sock.getsockname()[1])

    def _stop_udp_server(self) -> None:
        """Stop the UDP server if it's running."""
        if self._udp_server is None:
            return

        try:
            self._udp_server.close()
        finally:
            self._udp_server = None

        _LOGGER.debug("Stopped UDP server")


class VoiceAssistantUDPServer(asyncio.DatagramProtocol):
    """Receive UDP packets and forward them to the audio queue."""

    transport: asyncio.DatagramTransport | None = None
    remote_addr: tuple[str, int] | None = None

    def __init__(
        self, audio_queue: asyncio.Queue[bytes | None], *args: Any, **kwargs: Any
    ) -> None:
        """Initialize protocol."""
        super().__init__(*args, **kwargs)
        self._audio_queue = audio_queue

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Store transport for later use."""
        self.transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP packet."""
        if self.remote_addr is None:
            self.remote_addr = addr

        self._audio_queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        """Handle when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        """
        _LOGGER.error("ESPHome Voice Assistant UDP server error received: %s", exc)

        # Stop pipeline
        self._audio_queue.put_nowait(None)

    def close(self) -> None:
        """Close the receiver."""
        if self.transport is not None:
            self.transport.close()

        self.remote_addr = None

    def send_audio_bytes(self, data: bytes) -> None:
        """Send bytes to the device via UDP."""
        if self.transport is None:
            _LOGGER.error("No transport to send audio to")
            return

        if self.remote_addr is None:
            _LOGGER.error("No address to send audio to")
            return

        self.transport.sendto(data, self.remote_addr)
