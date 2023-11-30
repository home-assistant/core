"""Support for Wyoming satellite services."""
import asyncio
from collections.abc import AsyncGenerator
import io
import logging
from typing import Final
import wave

from wyoming.asr import Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.pipeline import PipelineStage, RunPipeline
from wyoming.satellite import RunSatellite
from wyoming.tts import Synthesize, SynthesizeVoice
from wyoming.vad import VoiceStarted, VoiceStopped
from wyoming.wake import Detect, Detection

from homeassistant.components import assist_pipeline, stt, tts
from homeassistant.components.assist_pipeline import select as pipeline_select
from homeassistant.core import Context, HomeAssistant

from .const import DOMAIN
from .data import WyomingService
from .devices import SatelliteDevice

_LOGGER = logging.getLogger()

_SAMPLES_PER_CHUNK: Final = 1024
_RECONNECT_SECONDS: Final = 10
_RESTART_SECONDS: Final = 3

# Wyoming stage -> Assist stage
_STAGES: dict[PipelineStage, assist_pipeline.PipelineStage] = {
    PipelineStage.WAKE: assist_pipeline.PipelineStage.WAKE_WORD,
    PipelineStage.ASR: assist_pipeline.PipelineStage.STT,
    PipelineStage.HANDLE: assist_pipeline.PipelineStage.INTENT,
    PipelineStage.TTS: assist_pipeline.PipelineStage.TTS,
}


class WyomingSatellite:
    """Remove voice satellite running the Wyoming protocol."""

    def __init__(
        self, hass: HomeAssistant, service: WyomingService, device: SatelliteDevice
    ) -> None:
        """Initialize satellite."""
        self.hass = hass
        self.service = service
        self.device = device
        self.is_enabled = True
        self.is_running = True

        self._client: AsyncTcpClient | None = None
        self._chunk_converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self._is_pipeline_running = False
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._pipeline_id: str | None = None
        self._device_updated_event = asyncio.Event()

    async def run(self) -> None:
        """Run and maintain a connection to satellite."""
        _LOGGER.debug("Running satellite task")
        self._pipeline_id = pipeline_select.get_chosen_pipeline(
            self.hass,
            DOMAIN,
            self.device.satellite_id,
        )
        self.is_enabled = self.device.is_enabled
        remove_listener = self.device.async_listen_update(self._device_updated)

        try:
            while self.is_running:
                try:
                    if not self.is_enabled:
                        await self._device_updated_event.wait()
                        if not self.is_running:
                            # Satellite was stopped while waiting to be enabled
                            break

                    await self._run_once()
                except asyncio.CancelledError:
                    raise
                except Exception:  # pylint: disable=broad-exception-caught
                    _LOGGER.exception(
                        "Unexpected error running satellite. Restarting in %s second(s)",
                        _RECONNECT_SECONDS,
                    )
                    await asyncio.sleep(_RESTART_SECONDS)
        finally:
            # Ensure sensor is off
            if self.device.is_active:
                self.device.set_is_active(False)

            remove_listener()

        _LOGGER.debug("Satellite task stopped")

    def stop(self) -> None:
        """Signal satellite task to stop running."""
        self.is_running = False

        # Unblock waiting for enabled
        self._device_updated_event.set()

    # -------------------------------------------------------------------------

    def _device_updated(self, device: SatelliteDevice) -> None:
        """Reacts to updated device settings."""
        pipeline_id = pipeline_select.get_chosen_pipeline(
            self.hass,
            DOMAIN,
            self.device.satellite_id,
        )

        stop_pipeline = False
        if self._pipeline_id != pipeline_id:
            # Pipeline has changed
            self._pipeline_id = pipeline_id
            stop_pipeline = True

        if self.is_enabled and (not self.device.is_enabled):
            stop_pipeline = True

        self.is_enabled = self.device.is_enabled
        self._device_updated_event.set()
        self._device_updated_event.clear()

        if stop_pipeline:
            self._audio_queue.put_nowait(None)

    async def _run_once(self) -> None:
        """Run pipelines until an error occurs."""
        if self.device.is_active:
            self.device.set_is_active(False)

        while True:
            try:
                await self._connect()
                break
            except ConnectionError:
                _LOGGER.debug(
                    "Failed to connect to satellite. Reconnecting in %s second(s)",
                    _RECONNECT_SECONDS,
                )
                await asyncio.sleep(_RECONNECT_SECONDS)

        assert self._client is not None
        _LOGGER.debug("Connected to satellite")

        if not self.is_running:
            # Run was cancelled
            return

        # Tell satellite that we're ready
        await self._client.write_event(RunSatellite().event())

        # Wait until we get RunPipeline event
        run_pipeline: RunPipeline | None = None
        while True:
            run_event = await self._client.read_event()
            if run_event is None:
                raise ConnectionResetError("Satellite disconnected")

            if RunPipeline.is_type(run_event.type):
                run_pipeline = RunPipeline.from_event(run_event)
                break

            _LOGGER.debug("Unexpected event from satellite: %s", run_event)

        assert run_pipeline is not None
        _LOGGER.debug("Received run information: %s", run_pipeline)

        if not self.is_running:
            # Run was cancelled
            return

        start_stage = _STAGES.get(run_pipeline.start_stage)
        end_stage = _STAGES.get(run_pipeline.end_stage)

        if start_stage is None:
            raise ValueError(f"Invalid start stage: {start_stage}")

        if end_stage is None:
            raise ValueError(f"Invalid end stage: {end_stage}")

        # Each loop is a pipeline run
        while self.is_running and self.is_enabled:
            # Use select to get pipeline each time in case it's changed
            pipeline = assist_pipeline.async_get_pipeline(self.hass, self._pipeline_id)
            assert pipeline is not None

            # We will push audio in through a queue
            self._audio_queue = asyncio.Queue()
            stt_stream = self._stt_stream()

            # Start pipeline running
            _LOGGER.debug(
                "Starting pipeline %s from %s to %s",
                pipeline.name,
                start_stage,
                end_stage,
            )
            self._is_pipeline_running = True
            _pipeline_task = asyncio.create_task(
                assist_pipeline.async_pipeline_from_audio_stream(
                    self.hass,
                    context=Context(),
                    event_callback=self._event_callback,
                    stt_metadata=stt.SpeechMetadata(
                        language=pipeline.language,
                        format=stt.AudioFormats.WAV,
                        codec=stt.AudioCodecs.PCM,
                        bit_rate=stt.AudioBitRates.BITRATE_16,
                        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                        channel=stt.AudioChannels.CHANNEL_MONO,
                    ),
                    stt_stream=stt_stream,
                    start_stage=start_stage,
                    end_stage=end_stage,
                    tts_audio_output="wav",
                    pipeline_id=self._pipeline_id,
                )
            )

            while self._is_pipeline_running:
                client_event = await self._client.read_event()
                if client_event is None:
                    raise ConnectionResetError("Satellite disconnected")

                if AudioChunk.is_type(client_event.type):
                    # Microphone audio
                    chunk = AudioChunk.from_event(client_event)
                    chunk = self._chunk_converter.convert(chunk)
                    self._audio_queue.put_nowait(chunk.audio)
                else:
                    _LOGGER.debug("Unexpected event from satellite: %s", client_event)

            _LOGGER.debug("Pipeline finished")

    def _event_callback(self, event: assist_pipeline.PipelineEvent) -> None:
        """Translate pipeline events into Wyoming events."""
        assert self._client is not None

        if event.type == assist_pipeline.PipelineEventType.RUN_END:
            self._is_pipeline_running = False
            if self.device.is_active:
                self.device.set_is_active(False)
        elif event.type == assist_pipeline.PipelineEventType.WAKE_WORD_START:
            self.hass.add_job(self._client.write_event(Detect().event()))
        elif event.type == assist_pipeline.PipelineEventType.WAKE_WORD_END:
            # Wake word detection
            if not self.device.is_active:
                self.device.set_is_active(True)

            # Inform client of wake word detection
            if event.data and (wake_word_output := event.data.get("wake_word_output")):
                detection = Detection(
                    name=wake_word_output["wake_word_id"],
                    timestamp=wake_word_output.get("timestamp"),
                )
                self.hass.add_job(self._client.write_event(detection.event()))
        elif event.type == assist_pipeline.PipelineEventType.STT_START:
            # Speech-to-text
            if not self.device.is_active:
                self.device.set_is_active(True)
        elif event.type == assist_pipeline.PipelineEventType.STT_VAD_START:
            if event.data:
                self.hass.add_job(
                    self._client.write_event(
                        VoiceStarted(timestamp=event.data["timestamp"]).event()
                    )
                )
        elif event.type == assist_pipeline.PipelineEventType.STT_VAD_END:
            if event.data:
                self.hass.add_job(
                    self._client.write_event(
                        VoiceStopped(timestamp=event.data["timestamp"]).event()
                    )
                )
        elif event.type == assist_pipeline.PipelineEventType.STT_END:
            # Speech-to-text transcript
            if event.data:
                # Inform client of transript
                stt_text = event.data["stt_output"]["text"]
                self.hass.add_job(
                    self._client.write_event(Transcript(text=stt_text).event())
                )
        elif event.type == assist_pipeline.PipelineEventType.TTS_START:
            # Text-to-speech text
            if event.data:
                # Inform client of text
                self.hass.add_job(
                    self._client.write_event(
                        Synthesize(
                            text=event.data["tts_input"],
                            voice=SynthesizeVoice(
                                name=event.data["voice"],
                                language=event.data["language"],
                            ),
                        ).event()
                    )
                )
        elif event.type == assist_pipeline.PipelineEventType.TTS_END:
            # TTS stream
            if event.data and (tts_output := event.data["tts_output"]):
                media_id = tts_output["media_id"]
                self.hass.add_job(self._stream_tts(media_id))

    async def _connect(self) -> None:
        """Connect to satellite over TCP."""
        _LOGGER.debug(
            "Connecting to satellite at %s:%s", self.service.host, self.service.port
        )
        self._client = AsyncTcpClient(self.service.host, self.service.port)
        await self._client.connect()

    async def _stream_tts(self, media_id: str) -> None:
        """Stream TTS WAV audio to satellite in chunks."""
        assert self._client is not None

        extension, data = await tts.async_get_media_source_audio(self.hass, media_id)
        if extension != "wav":
            raise ValueError(f"Cannot stream audio format to satellite: {extension}")

        with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            sample_channels = wav_file.getnchannels()
            _LOGGER.debug("Streaming %s TTS sample(s)", wav_file.getnframes())

            timestamp = 0
            await self._client.write_event(
                AudioStart(
                    rate=sample_rate,
                    width=sample_width,
                    channels=sample_channels,
                    timestamp=timestamp,
                ).event()
            )

            # Stream audio chunks
            while audio_bytes := wav_file.readframes(_SAMPLES_PER_CHUNK):
                chunk = AudioChunk(
                    rate=sample_rate,
                    width=sample_width,
                    channels=sample_channels,
                    audio=audio_bytes,
                    timestamp=timestamp,
                )
                await self._client.write_event(chunk.event())
                timestamp += chunk.seconds

            await self._client.write_event(AudioStop(timestamp=timestamp).event())
            _LOGGER.debug("TTS streaming complete")

    async def _stt_stream(self) -> AsyncGenerator[bytes, None]:
        """Yield audio chunks from a queue."""
        is_first_chunk = True
        while chunk := await self._audio_queue.get():
            if is_first_chunk:
                is_first_chunk = False
                _LOGGER.debug("Receiving audio from satellite")

            yield chunk
