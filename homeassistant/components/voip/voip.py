import asyncio
import functools
import logging
import math
from pathlib import Path
import socket
import time
import wave

import async_timeout

from homeassistant.components import stt, tts
from homeassistant.components.voice_assistant.pipeline import (
    Pipeline,
    PipelineEvent,
    PipelineEventType,
    PipelineInput,
    PipelineRun,
    PipelineStage,
    async_get_pipeline,
)
from homeassistant.components.voice_assistant.vad import VoiceCommandSegmenter
from homeassistant.core import Context, HomeAssistant

from .rtp_audio import RtpOpusInput, RtpOpusOutput
from .sip import CallInfo, SipDatagramProtocol

_LOGGER = logging.getLogger(__name__)


class VoipDatagramProtocol(SipDatagramProtocol):
    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__()
        self.hass = hass

    def on_call(self, call_info: CallInfo):
        """Callback for incoming call."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        # Bind to a random UDP port
        sock.bind((call_info.server_ip, 0))
        rtp_ip, rtp_port = sock.getsockname()
        _LOGGER.debug(
            "Starting RTP server on ip=%s, port=%s",
            rtp_ip,
            rtp_port,
        )

        language = self.hass.config.language
        if language == "en":
            language = "en-US"

        pipeline = async_get_pipeline(
            self.hass,
            language=language,
        )
        assert pipeline is not None

        self.hass.async_create_background_task(
            self.hass.loop.create_datagram_endpoint(
                lambda: PipelineDatagramProtocol(
                    self.hass,
                    pipeline,
                ),
                (rtp_ip, rtp_port),
            ),
            "voip_pipeline",
        )

        # self.hass.async_create_task(
        #     self.hass.loop.create_datagram_endpoint(
        #         lambda: MediaOutputDatagramProtocol(
        #             self.hass,
        #             "/home/hansenm/opt/homeassistant/config/media/apope_lincoln.wav",
        #             silence_before=0.5,
        #         ),
        #         (rtp_ip, rtp_port),
        #     )
        # )

        self.answer(call_info, rtp_port)


class PipelineDatagramProtocol(asyncio.DatagramProtocol):
    """Send a WAV file to an RTP client."""

    def __init__(
        self,
        hass: HomeAssistant,
        pipeline: Pipeline,
    ) -> None:
        self.hass = hass
        self.pipeline = pipeline
        self.transport = None
        self.addr = None

        self._audio_queue: "asyncio.Queue[bytes]" = asyncio.Queue()
        self._rtp_input = RtpOpusInput()
        self._rtp_output = RtpOpusOutput()
        self._pipeline_task: asyncio.Task | None = None

    def connection_made(self, transport):
        self.transport = transport
        _LOGGER.debug(
            "Started pipeline server on %s",
            self.transport.get_extra_info("sockname"),
        )

    def datagram_received(self, data, addr):
        if self.addr is None:
            self.addr = addr

        if self._pipeline_task is None:
            # Clear audio queue
            while not self._audio_queue.empty():
                self._audio_queue.get_nowait()

            self._pipeline_task = self.hass.async_create_background_task(
                self._run_pipeline(),
                "voip_pipeline_run",
            )

        # STT expects 16Khz mono with 16-bit samples
        audio_bytes = self._rtp_input.process_packet(
            data,
            16000,
            2,
            1,
        )
        self._audio_queue.put_nowait(audio_bytes)

    async def _run_pipeline(self, timeout: float = 30.0) -> None:
        _LOGGER.debug("Starting pipeline")

        async def stt_stream():
            segmenter = VoiceCommandSegmenter()
            while chunk := await self._audio_queue.get():
                if not segmenter.process(chunk):
                    # Voice command is finished
                    break

                yield chunk

        def event_callback(event: PipelineEvent):
            if (event.type == PipelineEventType.TTS_END) and event.data:
                media_id = event.data["tts_output"]["media_id"]
                self.hass.async_create_background_task(
                    self._send_audio(media_id),
                    "voip_pipeline_tts",
                )

        pipeline_input = PipelineInput(
            PipelineRun(
                hass=self.hass,
                context=Context(),
                pipeline=self.pipeline,
                start_stage=PipelineStage.STT,
                end_stage=PipelineStage.TTS,
                event_callback=event_callback,
            ),
            stt_metadata=stt.SpeechMetadata(
                language=self.pipeline.language,
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=stt_stream(),
        )

        try:
            await pipeline_input.validate()

            async with async_timeout.timeout(timeout):
                await pipeline_input.execute()
        except asyncio.TimeoutError:
            # Expected after caller hangs up
            pass
        finally:
            # Allow pipeline to run again
            self._pipeline_task = None

    async def _send_audio(self, media_id: str) -> None:
        """Sends TTS audio to caller via RTP."""
        assert self.transport is not None
        _extension, audio_bytes = await tts.async_get_media_source_audio(
            self.hass,
            media_id,
        )

        # Assume TTS audio is 16Khz 16-bit mono
        rate = 16000
        width = 2
        channels = 1
        bytes_per_frame = self._rtp_output.opus_frame_size * width * channels

        seconds_per_rtp = self._rtp_output.opus_frame_size / self._rtp_output.opus_rate
        total_samples = len(audio_bytes) // (width * channels)
        num_frames = int(
            math.ceil(
                total_samples / self._rtp_output.opus_frame_size,
            )
        )
        for i in range(num_frames):
            offset = i * self._rtp_output.opus_frame_size * width * channels
            chunk = audio_bytes[offset : offset + bytes_per_frame]
            for rtp_bytes in self._rtp_output.process_audio(
                chunk,
                rate,
                width,
                channels,
                is_end=i >= num_frames,
            ):
                self.transport.sendto(rtp_bytes, self.addr)

                # Wait almost the full amount of time for the chunk.
                #
                # Sending too fast will cause the phone to skip chunks,
                # since it doesn't seem to have a very large buffer.
                #
                # Sending too slow will cause audio artifacts if there is
                # network jitter, which is why programs like GStreamer are
                # much better at this.
                await asyncio.sleep(seconds_per_rtp * 0.99)


class MediaOutputDatagramProtocol(asyncio.DatagramProtocol):
    """Send a WAV file to an RTP client."""

    def __init__(
        self,
        hass: HomeAssistant,
        wav_path: str | Path,
        silence_before: float = 0.0,
    ) -> None:
        self.hass = hass
        self.transport = None
        self.silence_before = silence_before
        self.wav_path = str(wav_path)
        self._rtp_output = RtpOpusOutput()
        self._media_sent = False

    def connection_made(self, transport):
        self.transport = transport
        _LOGGER.debug(
            "Started media output server on %s",
            self.transport.get_extra_info("sockname"),
        )

    def datagram_received(self, data, addr):
        # Send media when first packet is received from caller
        if self._media_sent:
            return

        self._media_sent = True

        # Run in executor since we're doing media encoding and I/O.
        self.hass.async_add_executor_job(
            functools.partial(
                self._send_media,
                addr,
            )
        )

    def _send_media(self, addr):
        assert self.transport is not None

        # Pause before sending to allow time for user to pick up phone.
        time.sleep(self.silence_before)

        wav_file: wave.Wave_read = wave.open(self.wav_path, "rb")
        with wav_file:
            rate = wav_file.getframerate()
            width = wav_file.getsampwidth()
            channels = wav_file.getnchannels()
            frames_left = wav_file.getnframes()
            seconds_per_rtp = (
                self._rtp_output.opus_frame_size / self._rtp_output.opus_rate
            )

            while chunk := wav_file.readframes(self._rtp_output.opus_frame_size):
                frames_in_chunk = len(chunk) // (width * channels)
                frames_left -= frames_in_chunk
                for rtp_bytes in self._rtp_output.process_audio(
                    chunk,
                    rate,
                    width,
                    channels,
                    is_end=frames_left <= 0,
                ):
                    # _LOGGER.debug(len(rtp_bytes))
                    self.transport.sendto(rtp_bytes, addr)

                    # Wait almost the full amount of time for the chunk.
                    #
                    # Sending too fast will cause the phone to skip chunks,
                    # since it doesn't seem to have a very large buffer.
                    #
                    # Sending too slow will cause audio artifacts if there is
                    # network jitter, which is why programs like GStreamer are
                    # much better at this.
                    time.sleep(seconds_per_rtp * 0.99)

        # Done
        self.transport.close()
        self.transport = None
