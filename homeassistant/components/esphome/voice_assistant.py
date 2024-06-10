"""ESPHome voice assistant support."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Callable
import io
import logging
import socket
from typing import cast
import wave

from aioesphomeapi import (
    APIClient,
    VoiceAssistantAudioSettings,
    VoiceAssistantCommandFlag,
    VoiceAssistantEventType,
    VoiceAssistantFeature,
    VoiceAssistantTimerEventType,
)

from homeassistant.components import stt, tts
from homeassistant.components.assist_pipeline import (
    AudioSettings,
    PipelineEvent,
    PipelineEventType,
    PipelineNotFound,
    PipelineStage,
    WakeWordSettings,
    async_pipeline_from_audio_stream,
    select as pipeline_select,
)
from homeassistant.components.assist_pipeline.error import (
    WakeWordDetectionAborted,
    WakeWordDetectionError,
)
from homeassistant.components.intent.timers import TimerEventType, TimerInfo
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.core import Context, HomeAssistant, callback

from .const import DOMAIN
from .entry_data import RuntimeEntryData
from .enum_mapper import EsphomeEnumMapper

_LOGGER = logging.getLogger(__name__)

UDP_PORT = 0  # Set to 0 to let the OS pick a free random port
UDP_MAX_PACKET_SIZE = 1024

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


class VoiceAssistantPipeline:
    """Base abstract pipeline class."""

    started = False
    stop_requested = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: RuntimeEntryData,
        handle_event: Callable[[VoiceAssistantEventType, dict[str, str] | None], None],
        handle_finished: Callable[[], None],
    ) -> None:
        """Initialize the pipeline."""
        self.context = Context()
        self.hass = hass
        self.entry_data = entry_data
        assert entry_data.device_info is not None
        self.device_info = entry_data.device_info

        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.handle_event = handle_event
        self.handle_finished = handle_finished
        self._tts_done = asyncio.Event()
        self._tts_task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        """True if the pipeline is started and hasn't been asked to stop."""
        return self.started and (not self.stop_requested)

    async def _iterate_packets(self) -> AsyncIterable[bytes]:
        """Iterate over incoming packets."""
        while data := await self.queue.get():
            if not self.is_running:
                break

            yield data

    def _event_callback(self, event: PipelineEvent) -> None:
        """Handle pipeline events."""

        try:
            event_type = _VOICE_ASSISTANT_EVENT_TYPES.from_hass(event.type)
        except KeyError:
            _LOGGER.debug("Received unknown pipeline event type: %s", event.type)
            return

        data_to_send = None
        error = False
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
            tts_output = event.data["tts_output"]
            if tts_output:
                path = tts_output["url"]
                url = async_process_play_media_url(self.hass, path)
                data_to_send = {"url": url}

                if (
                    self.device_info.voice_assistant_feature_flags_compat(
                        self.entry_data.api_version
                    )
                    & VoiceAssistantFeature.SPEAKER
                ):
                    media_id = tts_output["media_id"]
                    self._tts_task = self.hass.async_create_background_task(
                        self._send_tts(media_id), "esphome_voice_assistant_tts"
                    )
                else:
                    self._tts_done.set()
            else:
                # Empty TTS response
                data_to_send = {}
                self._tts_done.set()
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_WAKE_WORD_END:
            assert event.data is not None
            if not event.data["wake_word_output"]:
                event_type = VoiceAssistantEventType.VOICE_ASSISTANT_ERROR
                data_to_send = {
                    "code": "no_wake_word",
                    "message": "No wake word detected",
                }
                error = True
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_ERROR:
            assert event.data is not None
            data_to_send = {
                "code": event.data["code"],
                "message": event.data["message"],
            }
            error = True

        self.handle_event(event_type, data_to_send)
        if error:
            self._tts_done.set()
            self.handle_finished()

    async def run_pipeline(
        self,
        device_id: str,
        conversation_id: str | None,
        flags: int = 0,
        audio_settings: VoiceAssistantAudioSettings | None = None,
        wake_word_phrase: str | None = None,
    ) -> None:
        """Run the Voice Assistant pipeline."""
        if audio_settings is None or audio_settings.volume_multiplier == 0:
            audio_settings = VoiceAssistantAudioSettings()

        if (
            self.device_info.voice_assistant_feature_flags_compat(
                self.entry_data.api_version
            )
            & VoiceAssistantFeature.SPEAKER
        ):
            tts_audio_output = "wav"
        else:
            tts_audio_output = "mp3"

        _LOGGER.debug("Starting pipeline")
        if flags & VoiceAssistantCommandFlag.USE_WAKE_WORD:
            start_stage = PipelineStage.WAKE_WORD
        else:
            start_stage = PipelineStage.STT
        try:
            await async_pipeline_from_audio_stream(
                self.hass,
                context=self.context,
                event_callback=self._event_callback,
                stt_metadata=stt.SpeechMetadata(
                    language="",  # set in async_pipeline_from_audio_stream
                    format=stt.AudioFormats.WAV,
                    codec=stt.AudioCodecs.PCM,
                    bit_rate=stt.AudioBitRates.BITRATE_16,
                    sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                    channel=stt.AudioChannels.CHANNEL_MONO,
                ),
                stt_stream=self._iterate_packets(),
                pipeline_id=pipeline_select.get_chosen_pipeline(
                    self.hass, DOMAIN, self.device_info.mac_address
                ),
                conversation_id=conversation_id,
                device_id=device_id,
                tts_audio_output=tts_audio_output,
                start_stage=start_stage,
                wake_word_settings=WakeWordSettings(timeout=5),
                wake_word_phrase=wake_word_phrase,
                audio_settings=AudioSettings(
                    noise_suppression_level=audio_settings.noise_suppression_level,
                    auto_gain_dbfs=audio_settings.auto_gain,
                    volume_multiplier=audio_settings.volume_multiplier,
                    is_vad_enabled=bool(flags & VoiceAssistantCommandFlag.USE_VAD),
                ),
            )

            # Block until TTS is done sending
            await self._tts_done.wait()

            _LOGGER.debug("Pipeline finished")
        except PipelineNotFound as e:
            self.handle_event(
                VoiceAssistantEventType.VOICE_ASSISTANT_ERROR,
                {
                    "code": e.code,
                    "message": e.message,
                },
            )
            _LOGGER.warning("Pipeline not found")
        except WakeWordDetectionAborted:
            pass  # Wake word detection was aborted and `handle_finished` is enough.
        except WakeWordDetectionError as e:
            self.handle_event(
                VoiceAssistantEventType.VOICE_ASSISTANT_ERROR,
                {
                    "code": e.code,
                    "message": e.message,
                },
            )
        finally:
            self.handle_finished()

    async def _send_tts(self, media_id: str) -> None:
        """Send TTS audio to device via UDP."""
        # Always send stream start/end events
        self.handle_event(VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_START, {})

        try:
            if not self.is_running:
                return

            extension, data = await tts.async_get_media_source_audio(
                self.hass,
                media_id,
            )

            if extension != "wav":
                raise ValueError(f"Only WAV audio can be streamed, got {extension}")

            with io.BytesIO(data) as wav_io:
                with wave.open(wav_io, "rb") as wav_file:
                    sample_rate = wav_file.getframerate()
                    sample_width = wav_file.getsampwidth()
                    sample_channels = wav_file.getnchannels()

                    if (
                        (sample_rate != 16000)
                        or (sample_width != 2)
                        or (sample_channels != 1)
                    ):
                        raise ValueError(
                            "Expected rate/width/channels as 16000/2/1,"
                            " got {sample_rate}/{sample_width}/{sample_channels}}"
                        )

                audio_bytes = wav_file.readframes(wav_file.getnframes())

            audio_bytes_size = len(audio_bytes)

            _LOGGER.debug("Sending %d bytes of audio", audio_bytes_size)

            bytes_per_sample = stt.AudioBitRates.BITRATE_16 // 8
            sample_offset = 0
            samples_left = audio_bytes_size // bytes_per_sample

            while (samples_left > 0) and self.is_running:
                bytes_offset = sample_offset * bytes_per_sample
                chunk: bytes = audio_bytes[bytes_offset : bytes_offset + 1024]
                samples_in_chunk = len(chunk) // bytes_per_sample
                samples_left -= samples_in_chunk

                self.send_audio_bytes(chunk)
                await asyncio.sleep(
                    samples_in_chunk / stt.AudioSampleRates.SAMPLERATE_16000 * 0.9
                )

                sample_offset += samples_in_chunk
        finally:
            self.handle_event(
                VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_END, {}
            )
            self._tts_task = None
            self._tts_done.set()

    def send_audio_bytes(self, data: bytes) -> None:
        """Send bytes to the device."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop the pipeline."""
        self.queue.put_nowait(b"")


class VoiceAssistantUDPPipeline(asyncio.DatagramProtocol, VoiceAssistantPipeline):
    """Receive UDP packets and forward them to the voice assistant."""

    transport: asyncio.DatagramTransport | None = None
    remote_addr: tuple[str, int] | None = None

    async def start_server(self) -> int:
        """Start accepting connections."""

        def accept_connection() -> VoiceAssistantUDPPipeline:
            """Accept connection."""
            if self.started:
                raise RuntimeError("Can only start once")
            if self.stop_requested:
                raise RuntimeError("No longer accepting connections")

            self.started = True
            return self

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        sock.bind(("", UDP_PORT))

        await asyncio.get_running_loop().create_datagram_endpoint(
            accept_connection, sock=sock
        )

        return cast(int, sock.getsockname()[1])

    @callback
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Store transport for later use."""
        self.transport = cast(asyncio.DatagramTransport, transport)

    @callback
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP packet."""
        if not self.is_running:
            return
        if self.remote_addr is None:
            self.remote_addr = addr
        self.queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        """Handle when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        """
        _LOGGER.error("ESPHome Voice Assistant UDP server error received: %s", exc)
        self.handle_finished()

    @callback
    def stop(self) -> None:
        """Stop the receiver."""
        super().stop()
        self.close()

    def close(self) -> None:
        """Close the receiver."""
        self.started = False
        self.stop_requested = True

        if self.transport is not None:
            self.transport.close()

    def send_audio_bytes(self, data: bytes) -> None:
        """Send bytes to the device via UDP."""
        if self.transport is None:
            _LOGGER.error("No transport to send audio to")
            return
        self.transport.sendto(data, self.remote_addr)


class VoiceAssistantAPIPipeline(VoiceAssistantPipeline):
    """Send audio to the voice assistant via the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: RuntimeEntryData,
        handle_event: Callable[[VoiceAssistantEventType, dict[str, str] | None], None],
        handle_finished: Callable[[], None],
        api_client: APIClient,
    ) -> None:
        """Initialize the pipeline."""
        super().__init__(hass, entry_data, handle_event, handle_finished)
        self.api_client = api_client
        self.started = True

    def send_audio_bytes(self, data: bytes) -> None:
        """Send bytes to the device via the API."""
        self.api_client.send_voice_assistant_audio(data)

    @callback
    def receive_audio_bytes(self, data: bytes) -> None:
        """Receive audio bytes from the device."""
        if not self.is_running:
            return
        self.queue.put_nowait(data)

    @callback
    def stop(self) -> None:
        """Stop the pipeline."""
        super().stop()

        self.started = False
        self.stop_requested = True


def handle_timer_event(
    api_client: APIClient, event_type: TimerEventType, timer_info: TimerInfo
) -> None:
    """Handle timer events."""
    try:
        native_event_type = _TIMER_EVENT_TYPES.from_hass(event_type)
    except KeyError:
        _LOGGER.debug("Received unknown timer event type: %s", event_type)
        return

    api_client.send_voice_assistant_timer_event(
        native_event_type,
        timer_info.id,
        timer_info.name,
        timer_info.seconds,
        timer_info.seconds_left,
        timer_info.is_active,
    )
