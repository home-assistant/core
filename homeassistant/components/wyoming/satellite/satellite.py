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
from wyoming.wake import Detection

from homeassistant.components import assist_pipeline, stt, tts
from homeassistant.core import Context, HomeAssistant

from ..data import WyomingService

_LOGGER = logging.getLogger()

_SAMPLES_PER_CHUNK: Final = 1024
_RECONNECT_SECONDS: Final = 10
_RESTART_SECONDS: Final = 3


class WyomingSatellite:
    """Remove voice satellite running the Wyoming protocol."""

    def __init__(self, hass: HomeAssistant, service: WyomingService) -> None:
        """Initialize satellite."""
        self.hass = hass
        self.service = service
        self._client: AsyncTcpClient | None = None
        self._chunk_converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self._is_pipeline_running = False

    async def run(self) -> None:
        """Run and maintain a connection to satellite."""
        while self.hass.is_running:
            try:
                await self._run_once()
            except Exception:  # pylint: disable=broad-exception-caught
                _LOGGER.exception(
                    "Unexpected error running satellite. Restarting in %s second(s)",
                    _RECONNECT_SECONDS,
                )
                await asyncio.sleep(_RESTART_SECONDS)

    async def _run_once(self) -> None:
        """Run pipelines until an error occurs."""
        while True:
            try:
                await self._connect()
                break
            except ConnectionError:
                _LOGGER.exception(
                    "Failed to connect to satellite. Reconnecting in %s second(s)",
                    _RECONNECT_SECONDS,
                )
                await asyncio.sleep(_RECONNECT_SECONDS)

        assert self._client is not None
        _LOGGER.debug("Connected to satellite")

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

        start_stage = _convert_stage(run_pipeline.start_stage)
        end_stage = _convert_stage(run_pipeline.end_stage)

        # Default pipeline
        pipeline = assist_pipeline.async_get_pipeline(self.hass)

        while True:
            # We will push audio in through a queue
            audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
            stt_stream = _stt_stream(audio_queue)

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
                    pipeline_id=pipeline.id,
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
                    audio_queue.put_nowait(chunk.audio)
                else:
                    _LOGGER.debug("Unexpected event from satellite: %s", client_event)

            _LOGGER.debug("Pipeline finished")

    def _event_callback(self, event: assist_pipeline.PipelineEvent) -> None:
        """Translate pipeline events into Wyoming events."""
        assert self._client is not None

        if event.type == assist_pipeline.PipelineEventType.RUN_END:
            self._is_pipeline_running = False
        elif event.type == assist_pipeline.PipelineEventType.WAKE_WORD_END:
            # Wake word detection
            detection = Detection()
            if event.data:
                wake_word_output = event.data["wake_word_output"]
                detection.name = wake_word_output["wake_word_id"]
                detection.timestamp = wake_word_output.get("timestamp")

            self.hass.add_job(self._client.write_event(detection.event()))
        elif event.type == assist_pipeline.PipelineEventType.STT_END:
            # STT transcript
            if event.data:
                stt_text = event.data["stt_output"]["text"]
                self.hass.add_job(
                    self._client.write_event(Transcript(text=stt_text).event())
                )
        elif event.type == assist_pipeline.PipelineEventType.TTS_START:
            # TTS text
            if event.data:
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
            if event.data:
                media_id = event.data["tts_output"]["media_id"]
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

            await self._client.write_event(
                AudioStart(
                    rate=sample_rate,
                    width=sample_width,
                    channels=sample_channels,
                ).event()
            )

            # Stream audio chunks
            while audio_bytes := wav_file.readframes(_SAMPLES_PER_CHUNK):
                await self._client.write_event(
                    AudioChunk(
                        rate=sample_rate,
                        width=sample_width,
                        channels=sample_channels,
                        audio=audio_bytes,
                    ).event()
                )

            await self._client.write_event(AudioStop().event())
            _LOGGER.debug("TTS streaming complete")


# -----------------------------------------------------------------------------


async def _stt_stream(
    audio_queue: asyncio.Queue[bytes],
) -> AsyncGenerator[bytes, None]:
    """Yield audio chunks from a queue."""
    is_first_chunk = True
    while chunk := await audio_queue.get():
        if is_first_chunk:
            is_first_chunk = False
            _LOGGER.debug("Receiving audio from satellite")

        yield chunk


def _convert_stage(wyoming_stage: PipelineStage) -> assist_pipeline.PipelineStage:
    """Convert Wyoming pipeline stage to Assist pipeline stage."""
    if wyoming_stage == PipelineStage.WAKE:
        return assist_pipeline.PipelineStage.WAKE_WORD

    if wyoming_stage == PipelineStage.ASR:
        return assist_pipeline.PipelineStage.STT

    if wyoming_stage == PipelineStage.HANDLE:
        return assist_pipeline.PipelineStage.INTENT

    if wyoming_stage == PipelineStage.TTS:
        return assist_pipeline.PipelineStage.TTS

    raise ValueError(f"Unknown Wyoming pipeline stage: {wyoming_stage}")
