"""Voice over IP (VoIP) implementation."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import async_timeout
from voip_utils import CallInfo, RtpDatagramProtocol, SdpInfo, VoipDatagramProtocol

from homeassistant.components import stt, tts
from homeassistant.components.assist_pipeline import (
    Pipeline,
    PipelineEvent,
    PipelineEventType,
    async_pipeline_from_audio_stream,
)
from homeassistant.components.assist_pipeline.vad import VoiceCommandSegmenter
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .devices import VoIPDevices

_LOGGER = logging.getLogger(__name__)


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
            protocol_factory=lambda call_info: PipelineRtpDatagramProtocol(
                hass,
                hass.config.language,
            ),
        )
        self.devices = devices

    def is_valid_call(self, call_info: CallInfo) -> bool:
        """Filter calls."""
        return self.devices.async_allow_call(call_info)


class PipelineRtpDatagramProtocol(RtpDatagramProtocol):
    """Run a voice assistant pipeline in a loop for a VoIP call."""

    def __init__(
        self,
        hass: HomeAssistant,
        language: str,
        pipeline_timeout: float = 30.0,
        audio_timeout: float = 2.0,
    ) -> None:
        """Set up pipeline RTP server."""
        # STT expects 16Khz mono with 16-bit samples
        super().__init__(rate=16000, width=2, channels=1)

        self.hass = hass
        self.language = language
        self.pipeline: Pipeline | None = None
        self.pipeline_timeout = pipeline_timeout
        self.audio_timeout = audio_timeout

        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._pipeline_task: asyncio.Task | None = None
        self._conversation_id: str | None = None

    def connection_made(self, transport):
        """Server is ready."""
        self.transport = transport

    def on_chunk(self, audio_bytes: bytes) -> None:
        """Handle raw audio chunk."""
        if self._pipeline_task is None:
            # Clear audio queue
            while not self._audio_queue.empty():
                self._audio_queue.get_nowait()

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
        _LOGGER.debug("Starting pipeline")

        async def stt_stream():
            segmenter = VoiceCommandSegmenter()

            try:
                # Timeout if no audio comes in for a while.
                # This means the caller hung up.
                async with async_timeout.timeout(self.audio_timeout):
                    chunk = await self._audio_queue.get()

                while chunk:
                    if not segmenter.process(chunk):
                        # Voice command is finished
                        break

                    yield chunk

                    async with async_timeout.timeout(self.audio_timeout):
                        chunk = await self._audio_queue.get()
            except asyncio.TimeoutError:
                # Expected after caller hangs up
                _LOGGER.debug("Audio timeout")

                if self.transport is not None:
                    self.transport.close()
                    self.transport = None

        try:
            # Run pipeline with a timeout
            async with async_timeout.timeout(self.pipeline_timeout):
                await async_pipeline_from_audio_stream(
                    self.hass,
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
                    language=self.language,
                    conversation_id=self._conversation_id,
                    tts_options={tts.ATTR_AUDIO_OUTPUT: "raw"},
                )

        except asyncio.TimeoutError:
            # Expected after caller hangs up
            _LOGGER.debug("Pipeline timeout")

            if self.transport is not None:
                self.transport.close()
                self.transport = None
        finally:
            # Allow pipeline to run again
            self._pipeline_task = None

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
                self._send_media(media_id),
                "voip_pipeline_tts",
            )

    async def _send_media(self, media_id: str) -> None:
        """Send TTS audio to caller via RTP."""
        if self.transport is None:
            return

        _extension, audio_bytes = await tts.async_get_media_source_audio(
            self.hass,
            media_id,
        )

        _LOGGER.debug("Sending %s byte(s) of audio", len(audio_bytes))

        # Assume TTS audio is 16Khz 16-bit mono
        await self.send_audio(audio_bytes, rate=16000, width=2, channels=1)
