"""Voice over IP (VoIP) implementation."""

from __future__ import annotations

import asyncio
from functools import partial
import io
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING
import wave

from voip_utils import (
    CallInfo,
    RtcpState,
    RtpDatagramProtocol,
    SdpInfo,
    VoipDatagramProtocol,
)

from homeassistant.components import assist_satellite, tts
from homeassistant.components.assist_pipeline import (
    Pipeline,
    PipelineEvent,
    PipelineEventType,
    PipelineNotFound,
    async_audio_stream_from_queue,
    async_get_pipeline,
    select as pipeline_select,
)
from homeassistant.components.assist_pipeline.vad import VadSensitivity
from homeassistant.components.assist_satellite import async_get_satellite_entity
from homeassistant.const import __version__
from homeassistant.core import Context, HomeAssistant
from homeassistant.util.ulid import ulid_now

from .assist_satellite import VoipAssistSatellite
from .const import CHANNELS, DOMAIN, RATE, RTP_AUDIO_SETTINGS, WIDTH
from .devices import VoIPDevice

if TYPE_CHECKING:
    from .devices import VoIPDevices

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

    satellite = async_get_satellite_entity(hass, DOMAIN, voip_device.voip_id)
    assert isinstance(satellite, VoipAssistSatellite), "VoIP satellite not found"

    # Pipeline is properly configured
    return PipelineRtpDatagramProtocol(
        hass,
        devices,
        voip_device,
        satellite,
        Context(user_id=devices.config_entry.data["user"]),
        opus_payload_type=call_info.opus_payload_type,
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
            invalid_protocol_factory=(
                lambda call_info, rtcp_state: PreRecordMessageProtocol(
                    hass,
                    "not_configured.pcm",
                    opus_payload_type=call_info.opus_payload_type,
                    rtcp_state=rtcp_state,
                )
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
        voip_devices: VoIPDevices,
        voip_device: VoIPDevice,
        satellite: VoipAssistSatellite,
        context: Context,
        opus_payload_type: int,
        pipeline_timeout: float = 30.0,
        audio_chunk_timeout: float = 2.0,
        listening_tone_enabled: bool = True,
        processing_tone_enabled: bool = True,
        error_tone_enabled: bool = True,
        tone_delay: float = 0.2,
        tts_extra_timeout: float = 1.0,
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
        self.satellite = satellite
        self.voip_devices = voip_devices
        self.voip_device = voip_device
        self.pipeline: Pipeline | None = None
        self.pipeline_timeout = pipeline_timeout
        self.audio_chunk_timeout = audio_chunk_timeout
        self.listening_tone_enabled = listening_tone_enabled
        self.processing_tone_enabled = processing_tone_enabled
        self.error_tone_enabled = error_tone_enabled
        self.tone_delay = tone_delay
        self.tts_extra_timeout = tts_extra_timeout

        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._context = context
        self._pipeline_task: asyncio.Task | None = None
        self._tts_done = asyncio.Event()
        self._session_id: str | None = None
        self._tone_bytes: bytes | None = None
        self._processing_bytes: bytes | None = None
        self._processing_tone_done = asyncio.Event()
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
            self._pipeline_task = (
                self.voip_devices.config_entry.async_create_background_task(
                    self.hass,
                    self._run_pipeline(),
                    "voip_pipeline_run",
                )
            )

        self._audio_queue.put_nowait(audio_bytes)

    async def _run_pipeline(
        self,
    ) -> None:
        """Forward audio to pipeline STT and handle TTS."""
        if self._session_id is None:
            self._session_id = ulid_now()

        # Play listening tone at the start of each cycle
        if self.listening_tone_enabled:
            await self._play_listening_tone()

        try:
            await self.satellite.async_set_config(
                assist_satellite.SatelliteConfig(
                    default_pipeline=pipeline_select.get_chosen_pipeline(
                        self.hass,
                        DOMAIN,
                        self.voip_device.voip_id,
                    ),
                    finished_speaking_seconds=VadSensitivity.to_seconds(
                        pipeline_select.get_vad_sensitivity(
                            self.hass,
                            DOMAIN,
                            self.voip_device.voip_id,
                        )
                    ),
                )
            )

            self._tts_done.clear()

            # Run pipeline with a timeout
            _LOGGER.debug("Starting pipeline")
            async with asyncio.timeout(self.pipeline_timeout):
                await self.satellite._async_accept_pipeline_from_satellite(  # noqa: SLF001
                    context=self._context,
                    event_callback=self._event_callback,
                    audio_stream=async_audio_stream_from_queue(
                        self._audio_queue, timeout=self.audio_chunk_timeout
                    ),
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
        except (asyncio.CancelledError, TimeoutError):
            # Expected after caller hangs up
            _LOGGER.debug("Pipeline cancelled or timed out")
            self._session_id = None
            self.disconnect()
            self._clear_audio_queue()
        finally:
            # Allow pipeline to run again
            self._pipeline_task = None

    def _clear_audio_queue(self) -> None:
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()

    def _event_callback(self, event: PipelineEvent) -> None:
        if not event.data:
            return

        if event.type == PipelineEventType.STT_END:
            if self.processing_tone_enabled:
                self._processing_tone_done.clear()
                self.voip_devices.config_entry.async_create_background_task(
                    self.hass, self._play_processing_tone(), "voip_process_tone"
                )
        elif event.type == PipelineEventType.TTS_END:
            # Send TTS audio to caller over RTP
            tts_output = event.data["tts_output"]
            if tts_output:
                media_id = tts_output["media_id"]
                self.voip_devices.config_entry.async_create_background_task(
                    self.hass,
                    self._send_tts(media_id),
                    "voip_pipeline_tts",
                )
            else:
                # Empty TTS response
                self._tts_done.set()
        elif event.type == PipelineEventType.ERROR:
            # Play error tone instead of wait for TTS
            self._pipeline_error = True

    async def _send_tts(self, media_id: str) -> None:
        """Send TTS audio to caller via RTP."""
        try:
            if self.transport is None:
                return

            extension, data = await tts.async_get_media_source_audio(
                self.hass,
                media_id,
            )

            if extension != "wav":
                raise ValueError(f"Only WAV audio can be streamed, got {extension}")

            if self.processing_tone_enabled:
                await self._processing_tone_done.wait()

            with io.BytesIO(data) as wav_io:
                with wave.open(wav_io, "rb") as wav_file:
                    sample_rate = wav_file.getframerate()
                    sample_width = wav_file.getsampwidth()
                    sample_channels = wav_file.getnchannels()

                    if (
                        (sample_rate != RATE)
                        or (sample_width != WIDTH)
                        or (sample_channels != CHANNELS)
                    ):
                        raise ValueError(
                            f"Expected rate/width/channels as {RATE}/{WIDTH}/{CHANNELS},"
                            f" got {sample_rate}/{sample_width}/{sample_channels}"
                        )

                audio_bytes = wav_file.readframes(wav_file.getnframes())

            _LOGGER.debug("Sending %s byte(s) of audio", len(audio_bytes))

            # Time out 1 second after TTS audio should be finished
            tts_samples = len(audio_bytes) / (WIDTH * CHANNELS)
            tts_seconds = tts_samples / RATE

            async with asyncio.timeout(tts_seconds + self.tts_extra_timeout):
                # TTS audio is 16Khz 16-bit mono
                await self._async_send_audio(audio_bytes)
        except TimeoutError:
            _LOGGER.warning("TTS timeout")
            raise
        finally:
            # Signal pipeline to restart
            self._tts_done.set()

            # Update satellite state
            self.satellite.tts_response_finished()

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
        try:
            if self._processing_bytes is None:
                # Do I/O in executor
                self._processing_bytes = await self.hass.async_add_executor_job(
                    self._load_pcm,
                    "processing.pcm",
                )

            await self._async_send_audio(self._processing_bytes)
        finally:
            self._processing_tone_done.set()

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
