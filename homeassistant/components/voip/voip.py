"""Voice over IP (VoIP) implementation."""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterable, MutableSequence, Sequence
from functools import partial
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING

from voip_utils import (
    CallInfo,
    RtcpState,
    RtpDatagramProtocol,
    SdpInfo,
    VoipDatagramProtocol,
)

from homeassistant.components import stt, tts
from homeassistant.components.assist_pipeline import (
    Pipeline,
    PipelineEvent,
    PipelineEventType,
    PipelineNotFound,
    async_get_pipeline,
    async_pipeline_from_audio_stream,
    select as pipeline_select,
)
from homeassistant.components.assist_pipeline.vad import (
    VadSensitivity,
    VoiceCommandSegmenter,
)
from homeassistant.const import __version__
from homeassistant.core import Context, HomeAssistant
from homeassistant.util.ulid import ulid

from .const import CHANNELS, DOMAIN, RATE, RTP_AUDIO_SETTINGS, WIDTH

if TYPE_CHECKING:
    from .devices import VoIPDevice, VoIPDevices

_LOGGER = logging.getLogger(__name__)


def make_protocol(
    hass: HomeAssistant,
    devices: VoIPDevices,
    call_info: CallInfo,
    rtcp_state: RtcpState | None = None,
) -> VoipDatagramProtocol:
    """Plays a pre-recorded message if pipeline is misconfigured."""
    voip_device = devices.async_get_or_create(call_info)
    pipeline_id = pipeline_select.get_chosen_pipeline(
        hass,
        DOMAIN,
        voip_device.voip_id,
    )
    try:
        pipeline: Pipeline | None = async_get_pipeline(hass, pipeline_id)
    except PipelineNotFound:
        pipeline = None

    if (
        (pipeline is None)
        or (pipeline.stt_engine is None)
        or (pipeline.tts_engine is None)
    ):
        # Play pre-recorded message instead of failing
        return PreRecordMessageProtocol(
            hass,
            "problem.pcm",
            opus_payload_type=call_info.opus_payload_type,
            rtcp_state=rtcp_state,
        )

    vad_sensitivity = pipeline_select.get_vad_sensitivity(
        hass,
        DOMAIN,
        voip_device.voip_id,
    )

    # Pipeline is properly configured
    return PipelineRtpDatagramProtocol(
        hass,
        hass.config.language,
        voip_device,
        Context(user_id=devices.config_entry.data["user"]),
        opus_payload_type=call_info.opus_payload_type,
        silence_seconds=VadSensitivity.to_seconds(vad_sensitivity),
        rtcp_state=rtcp_state,
    )


class HassVoipDatagramProtocol(VoipDatagramProtocol):
    """HA UDP server for Voice over IP (VoIP)."""

    def __init__(self, hass: HomeAssistant, devices: VoIPDevices) -> None:
        """Set up VoIP call handler."""
        super().__init__(
            sdp_info=SdpInfo(
                username="homeassistant",
                id=time.monotonic_ns(),
                session_name="voip_hass",
                version=__version__,
            ),
            valid_protocol_factory=lambda call_info, rtcp_state: make_protocol(
                hass, devices, call_info, rtcp_state
            ),
            invalid_protocol_factory=lambda call_info, rtcp_state: PreRecordMessageProtocol(
                hass,
                "not_configured.pcm",
                opus_payload_type=call_info.opus_payload_type,
                rtcp_state=rtcp_state,
            ),
        )
        self.hass = hass
        self.devices = devices
        self._closed_event = asyncio.Event()

    def is_valid_call(self, call_info: CallInfo) -> bool:
        """Filter calls."""
        device = self.devices.async_get_or_create(call_info)
        return device.async_allow_call(self.hass)

    def connection_lost(self, exc):
        """Signal wait_closed when transport is completely closed."""
        self.hass.loop.call_soon_threadsafe(self._closed_event.set)

    async def wait_closed(self) -> None:
        """Wait for connection_lost to be called."""
        await self._closed_event.wait()


class PipelineRtpDatagramProtocol(RtpDatagramProtocol):
    """Run a voice assistant pipeline in a loop for a VoIP call."""

    def __init__(
        self,
        hass: HomeAssistant,
        language: str,
        voip_device: VoIPDevice,
        context: Context,
        opus_payload_type: int,
        pipeline_timeout: float = 30.0,
        audio_timeout: float = 2.0,
        buffered_chunks_before_speech: int = 100,
        listening_tone_enabled: bool = True,
        processing_tone_enabled: bool = True,
        error_tone_enabled: bool = True,
        tone_delay: float = 0.2,
        tts_extra_timeout: float = 1.0,
        silence_seconds: float = 1.0,
        rtcp_state: RtcpState | None = None,
    ) -> None:
        """Set up pipeline RTP server."""
        super().__init__(
            rate=RATE,
            width=WIDTH,
            channels=CHANNELS,
            opus_payload_type=opus_payload_type,
            rtcp_state=rtcp_state,
        )

        self.hass = hass
        self.language = language
        self.voip_device = voip_device
        self.pipeline: Pipeline | None = None
        self.pipeline_timeout = pipeline_timeout
        self.audio_timeout = audio_timeout
        self.buffered_chunks_before_speech = buffered_chunks_before_speech
        self.listening_tone_enabled = listening_tone_enabled
        self.processing_tone_enabled = processing_tone_enabled
        self.error_tone_enabled = error_tone_enabled
        self.tone_delay = tone_delay
        self.tts_extra_timeout = tts_extra_timeout
        self.silence_seconds = silence_seconds

        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._context = context
        self._conversation_id: str | None = None
        self._pipeline_task: asyncio.Task | None = None
        self._tts_done = asyncio.Event()
        self._session_id: str | None = None
        self._tone_bytes: bytes | None = None
        self._processing_bytes: bytes | None = None
        self._error_bytes: bytes | None = None
        self._pipeline_error: bool = False

    def connection_made(self, transport):
        """Server is ready."""
        super().connection_made(transport)
        self.voip_device.set_is_active(True)

    def connection_lost(self, exc):
        """Handle connection is lost or closed."""
        super().connection_lost(exc)
        self.voip_device.set_is_active(False)

    def on_chunk(self, audio_bytes: bytes) -> None:
        """Handle raw audio chunk."""
        if self._pipeline_task is None:
            self._clear_audio_queue()

            # Run pipeline until voice command finishes, then start over
            self._pipeline_task = self.hass.async_create_background_task(
                self._run_pipeline(),
                "voip_pipeline_run",
            )

        self._audio_queue.put_nowait(audio_bytes)

    async def _run_pipeline(
        self,
    ) -> None:
        """Forward audio to pipeline STT and handle TTS."""
        if self._session_id is None:
            self._session_id = ulid()

        # Play listening tone at the start of each cycle
        if self.listening_tone_enabled:
            await self._play_listening_tone()

        try:
            # Wait for speech before starting pipeline
            segmenter = VoiceCommandSegmenter(silence_seconds=self.silence_seconds)
            chunk_buffer: deque[bytes] = deque(
                maxlen=self.buffered_chunks_before_speech,
            )
            speech_detected = await self._wait_for_speech(
                segmenter,
                chunk_buffer,
            )
            if not speech_detected:
                _LOGGER.debug("No speech detected")
                return

            _LOGGER.debug("Starting pipeline")
            self._tts_done.clear()

            async def stt_stream():
                try:
                    async for chunk in self._segment_audio(
                        segmenter,
                        chunk_buffer,
                    ):
                        yield chunk

                    if self.processing_tone_enabled:
                        await self._play_processing_tone()
                except asyncio.TimeoutError:
                    # Expected after caller hangs up
                    _LOGGER.debug("Audio timeout")
                    self._session_id = None
                    self.disconnect()
                finally:
                    self._clear_audio_queue()

            # Run pipeline with a timeout
            async with asyncio.timeout(self.pipeline_timeout):
                await async_pipeline_from_audio_stream(
                    self.hass,
                    context=self._context,
                    event_callback=self._event_callback,
                    stt_metadata=stt.SpeechMetadata(
                        language="",  # set in async_pipeline_from_audio_stream
                        format=stt.AudioFormats.WAV,
                        codec=stt.AudioCodecs.PCM,
                        bit_rate=stt.AudioBitRates.BITRATE_16,
                        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                        channel=stt.AudioChannels.CHANNEL_MONO,
                    ),
                    stt_stream=stt_stream(),
                    pipeline_id=pipeline_select.get_chosen_pipeline(
                        self.hass, DOMAIN, self.voip_device.voip_id
                    ),
                    conversation_id=self._conversation_id,
                    device_id=self.voip_device.device_id,
                    tts_audio_output="raw",
                )

            if self._pipeline_error:
                self._pipeline_error = False
                if self.error_tone_enabled:
                    await self._play_error_tone()
            else:
                # Block until TTS is done speaking.
                #
                # This is set in _send_tts and has a timeout that's based on the
                # length of the TTS audio.
                await self._tts_done.wait()

            _LOGGER.debug("Pipeline finished")
        except PipelineNotFound:
            _LOGGER.warning("Pipeline not found")
        except asyncio.TimeoutError:
            # Expected after caller hangs up
            _LOGGER.debug("Pipeline timeout")
            self._session_id = None
            self.disconnect()
        finally:
            # Allow pipeline to run again
            self._pipeline_task = None

    async def _wait_for_speech(
        self,
        segmenter: VoiceCommandSegmenter,
        chunk_buffer: MutableSequence[bytes],
    ):
        """Buffer audio chunks until speech is detected.

        Returns True if speech was detected, False otherwise.
        """
        # Timeout if no audio comes in for a while.
        # This means the caller hung up.
        async with asyncio.timeout(self.audio_timeout):
            chunk = await self._audio_queue.get()

        while chunk:
            chunk_buffer.append(chunk)

            segmenter.process(chunk)
            if segmenter.in_command:
                # Buffer until command starts
                return True

            async with asyncio.timeout(self.audio_timeout):
                chunk = await self._audio_queue.get()

        return False

    async def _segment_audio(
        self,
        segmenter: VoiceCommandSegmenter,
        chunk_buffer: Sequence[bytes],
    ) -> AsyncIterable[bytes]:
        """Yield audio chunks until voice command has finished."""
        # Buffered chunks first
        for buffered_chunk in chunk_buffer:
            yield buffered_chunk

        # Timeout if no audio comes in for a while.
        # This means the caller hung up.
        async with asyncio.timeout(self.audio_timeout):
            chunk = await self._audio_queue.get()

        while chunk:
            if not segmenter.process(chunk):
                # Voice command is finished
                break

            yield chunk

            async with asyncio.timeout(self.audio_timeout):
                chunk = await self._audio_queue.get()

    def _clear_audio_queue(self) -> None:
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()

    def _event_callback(self, event: PipelineEvent):
        if not event.data:
            return

        if event.type == PipelineEventType.INTENT_END:
            # Capture conversation id
            self._conversation_id = event.data["intent_output"]["conversation_id"]
        elif event.type == PipelineEventType.TTS_END:
            # Send TTS audio to caller over RTP
            media_id = event.data["tts_output"]["media_id"]
            self.hass.async_create_background_task(
                self._send_tts(media_id),
                "voip_pipeline_tts",
            )
        elif event.type == PipelineEventType.ERROR:
            # Play error tone instead of wait for TTS
            self._pipeline_error = True

    async def _send_tts(self, media_id: str) -> None:
        """Send TTS audio to caller via RTP."""
        try:
            if self.transport is None:
                return

            _extension, audio_bytes = await tts.async_get_media_source_audio(
                self.hass,
                media_id,
            )

            _LOGGER.debug("Sending %s byte(s) of audio", len(audio_bytes))

            # Time out 1 second after TTS audio should be finished
            tts_samples = len(audio_bytes) / (WIDTH * CHANNELS)
            tts_seconds = tts_samples / RATE

            async with asyncio.timeout(tts_seconds + self.tts_extra_timeout):
                # Assume TTS audio is 16Khz 16-bit mono
                await self._async_send_audio(audio_bytes)
        except asyncio.TimeoutError as err:
            _LOGGER.warning("TTS timeout")
            raise err
        finally:
            # Signal pipeline to restart
            self._tts_done.set()

    async def _async_send_audio(self, audio_bytes: bytes, **kwargs):
        """Send audio in executor."""
        await self.hass.async_add_executor_job(
            partial(self.send_audio, audio_bytes, **RTP_AUDIO_SETTINGS, **kwargs)
        )

    async def _play_listening_tone(self) -> None:
        """Play a tone to indicate that Home Assistant is listening."""
        if self._tone_bytes is None:
            # Do I/O in executor
            self._tone_bytes = await self.hass.async_add_executor_job(
                self._load_pcm,
                "tone.pcm",
            )

        await self._async_send_audio(
            self._tone_bytes,
            silence_before=self.tone_delay,
        )

    async def _play_processing_tone(self) -> None:
        """Play a tone to indicate that Home Assistant is processing the voice command."""
        if self._processing_bytes is None:
            # Do I/O in executor
            self._processing_bytes = await self.hass.async_add_executor_job(
                self._load_pcm,
                "processing.pcm",
            )

        await self._async_send_audio(self._processing_bytes)

    async def _play_error_tone(self) -> None:
        """Play a tone to indicate a pipeline error occurred."""
        if self._error_bytes is None:
            # Do I/O in executor
            self._error_bytes = await self.hass.async_add_executor_job(
                self._load_pcm,
                "error.pcm",
            )

        await self._async_send_audio(self._error_bytes)

    def _load_pcm(self, file_name: str) -> bytes:
        """Load raw audio (16Khz, 16-bit mono)."""
        return (Path(__file__).parent / file_name).read_bytes()


class PreRecordMessageProtocol(RtpDatagramProtocol):
    """Plays a pre-recorded message on a loop."""

    def __init__(
        self,
        hass: HomeAssistant,
        file_name: str,
        opus_payload_type: int,
        message_delay: float = 1.0,
        loop_delay: float = 2.0,
        rtcp_state: RtcpState | None = None,
    ) -> None:
        """Set up RTP server."""
        super().__init__(
            rate=RATE,
            width=WIDTH,
            channels=CHANNELS,
            opus_payload_type=opus_payload_type,
            rtcp_state=rtcp_state,
        )
        self.hass = hass
        self.file_name = file_name
        self.message_delay = message_delay
        self.loop_delay = loop_delay
        self._audio_task: asyncio.Task | None = None
        self._audio_bytes: bytes | None = None

    def on_chunk(self, audio_bytes: bytes) -> None:
        """Handle raw audio chunk."""
        if self.transport is None:
            return

        if self._audio_bytes is None:
            # 16Khz, 16-bit mono audio message
            file_path = Path(__file__).parent / self.file_name
            self._audio_bytes = file_path.read_bytes()

        if self._audio_task is None:
            self._audio_task = self.hass.async_create_background_task(
                self._play_message(),
                "voip_not_connected",
            )

    async def _play_message(self) -> None:
        await self.hass.async_add_executor_job(
            partial(
                self.send_audio,
                self._audio_bytes,
                silence_before=self.message_delay,
                **RTP_AUDIO_SETTINGS,
            )
        )

        await asyncio.sleep(self.loop_delay)

        # Allow message to play again
        self._audio_task = None
