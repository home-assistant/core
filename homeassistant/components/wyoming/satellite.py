"""Support for Wyoming satellite services."""
import asyncio
from collections.abc import AsyncGenerator
import io
import logging
from typing import Final
import wave

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.error import Error
from wyoming.ping import Ping, Pong
from wyoming.pipeline import PipelineStage, RunPipeline
from wyoming.satellite import PauseSatellite, RunSatellite
from wyoming.tts import Synthesize, SynthesizeVoice
from wyoming.vad import VoiceStarted, VoiceStopped
from wyoming.wake import Detect, Detection

from homeassistant.components import assist_pipeline, stt, tts
from homeassistant.components.assist_pipeline import select as pipeline_select
from homeassistant.core import Context, HomeAssistant

from .const import DOMAIN
from .data import WyomingService
from .devices import SatelliteDevice

_LOGGER = logging.getLogger(__name__)

_SAMPLES_PER_CHUNK: Final = 1024
_RECONNECT_SECONDS: Final = 10
_RESTART_SECONDS: Final = 3
_PING_TIMEOUT: Final = 5
_PING_SEND_DELAY: Final = 2
_PIPELINE_FINISH_TIMEOUT: Final = 1

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
        self.is_running = True

        self._client: AsyncTcpClient | None = None
        self._chunk_converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self._is_pipeline_running = False
        self._pipeline_ended_event = asyncio.Event()
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._pipeline_id: str | None = None
        self._muted_changed_event = asyncio.Event()

        self.device.set_is_muted_listener(self._muted_changed)
        self.device.set_pipeline_listener(self._pipeline_changed)
        self.device.set_audio_settings_listener(self._audio_settings_changed)

    async def run(self) -> None:
        """Run and maintain a connection to satellite."""
        _LOGGER.debug("Running satellite task")

        try:
            while self.is_running:
                try:
                    # Check if satellite has been muted
                    while self.device.is_muted:
                        _LOGGER.debug("Satellite is muted")
                        await self.on_muted()
                        if not self.is_running:
                            # Satellite was stopped while waiting to be unmuted
                            return

                    # Connect and run pipeline loop
                    await self._connect_and_loop()
                except asyncio.CancelledError:
                    raise  # don't restart
                except Exception:  # pylint: disable=broad-exception-caught
                    # Ensure sensor is off (before restart)
                    self.device.set_is_active(False)

                    # Wait to restart
                    await self.on_restart()
        finally:
            # Ensure sensor is off (before stop)
            self.device.set_is_active(False)

            await self.on_stopped()

    def stop(self) -> None:
        """Signal satellite task to stop running."""
        # Tell satellite to stop running
        self._send_pause()

        # Stop task loop
        self.is_running = False

        # Unblock waiting for unmuted
        self._muted_changed_event.set()

    async def on_restart(self) -> None:
        """Block until pipeline loop will be restarted."""
        _LOGGER.warning(
            "Satellite has been disconnected. Reconnecting in %s second(s)",
            _RECONNECT_SECONDS,
        )
        await asyncio.sleep(_RESTART_SECONDS)

    async def on_reconnect(self) -> None:
        """Block until a reconnection attempt should be made."""
        _LOGGER.debug(
            "Failed to connect to satellite. Reconnecting in %s second(s)",
            _RECONNECT_SECONDS,
        )
        await asyncio.sleep(_RECONNECT_SECONDS)

    async def on_muted(self) -> None:
        """Block until device may be unmated again."""
        await self._muted_changed_event.wait()

    async def on_stopped(self) -> None:
        """Run when run() has fully stopped."""
        _LOGGER.debug("Satellite task stopped")

    # -------------------------------------------------------------------------

    def _send_pause(self) -> None:
        """Send a pause message to satellite."""
        if self._client is not None:
            self.hass.async_create_background_task(
                self._client.write_event(PauseSatellite().event()),
                "pause satellite",
            )

    def _muted_changed(self) -> None:
        """Run when device muted status changes."""
        if self.device.is_muted:
            # Cancel any running pipeline
            self._audio_queue.put_nowait(None)

            # Send pause event so satellite can react immediately
            self._send_pause()

        self._muted_changed_event.set()
        self._muted_changed_event.clear()

    def _pipeline_changed(self) -> None:
        """Run when device pipeline changes."""

        # Cancel any running pipeline
        self._audio_queue.put_nowait(None)

    def _audio_settings_changed(self) -> None:
        """Run when device audio settings."""

        # Cancel any running pipeline
        self._audio_queue.put_nowait(None)

    async def _connect_and_loop(self) -> None:
        """Connect to satellite and run pipelines until an error occurs."""
        while self.is_running and (not self.device.is_muted):
            try:
                await self._connect()
                break
            except ConnectionError:
                self._client = None  # client is not valid

                await self.on_reconnect()

        if self._client is None:
            return

        _LOGGER.debug("Connected to satellite")

        if (not self.is_running) or self.device.is_muted:
            # Run was cancelled or satellite was disabled during connection
            return

        # Tell satellite that we're ready
        await self._client.write_event(RunSatellite().event())

        # Run until stopped or muted
        while self.is_running and (not self.device.is_muted):
            await self._run_pipeline_loop()

    async def _run_pipeline_loop(self) -> None:
        """Run a pipeline one or more times."""
        assert self._client is not None
        run_pipeline: RunPipeline | None = None
        send_ping = True

        # Read events and check for pipeline end in parallel
        pipeline_ended_task = self.hass.async_create_background_task(
            self._pipeline_ended_event.wait(), "satellite pipeline ended"
        )
        client_event_task = self.hass.async_create_background_task(
            self._client.read_event(), "satellite event read"
        )
        pending = {pipeline_ended_task, client_event_task}

        while self.is_running and (not self.device.is_muted):
            if send_ping:
                # Ensure satellite is still connected
                send_ping = False
                self.hass.async_create_background_task(
                    self._send_delayed_ping(), "ping satellite"
                )

            async with asyncio.timeout(_PING_TIMEOUT):
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                if pipeline_ended_task in done:
                    # Pipeline run end event was received
                    _LOGGER.debug("Pipeline finished")
                    self._pipeline_ended_event.clear()
                    pipeline_ended_task = self.hass.async_create_background_task(
                        self._pipeline_ended_event.wait(), "satellite pipeline ended"
                    )
                    pending.add(pipeline_ended_task)

                    if (run_pipeline is not None) and run_pipeline.restart_on_end:
                        # Automatically restart pipeline.
                        # Used with "always on" streaming satellites.
                        self._run_pipeline_once(run_pipeline)
                        continue

                if client_event_task not in done:
                    continue

                client_event = client_event_task.result()
                if client_event is None:
                    raise ConnectionResetError("Satellite disconnected")

                if Pong.is_type(client_event.type):
                    # Satellite is still there, send next ping
                    send_ping = True
                elif Ping.is_type(client_event.type):
                    # Respond to ping from satellite
                    ping = Ping.from_event(client_event)
                    await self._client.write_event(Pong(text=ping.text).event())
                elif RunPipeline.is_type(client_event.type):
                    # Satellite requested pipeline run
                    run_pipeline = RunPipeline.from_event(client_event)
                    self._run_pipeline_once(run_pipeline)
                elif (
                    AudioChunk.is_type(client_event.type) and self._is_pipeline_running
                ):
                    # Microphone audio
                    chunk = AudioChunk.from_event(client_event)
                    chunk = self._chunk_converter.convert(chunk)
                    self._audio_queue.put_nowait(chunk.audio)
                elif AudioStop.is_type(client_event.type) and self._is_pipeline_running:
                    # Stop pipeline
                    _LOGGER.debug("Client requested pipeline to stop")
                    self._audio_queue.put_nowait(b"")
                else:
                    _LOGGER.debug("Unexpected event from satellite: %s", client_event)

                # Next event
                client_event_task = self.hass.async_create_background_task(
                    self._client.read_event(), "satellite event read"
                )
                pending.add(client_event_task)

    def _run_pipeline_once(self, run_pipeline: RunPipeline) -> None:
        """Run a pipeline once."""
        _LOGGER.debug("Received run information: %s", run_pipeline)

        start_stage = _STAGES.get(run_pipeline.start_stage)
        end_stage = _STAGES.get(run_pipeline.end_stage)

        if start_stage is None:
            raise ValueError(f"Invalid start stage: {start_stage}")

        if end_stage is None:
            raise ValueError(f"Invalid end stage: {end_stage}")

        pipeline_id = pipeline_select.get_chosen_pipeline(
            self.hass,
            DOMAIN,
            self.device.satellite_id,
        )
        pipeline = assist_pipeline.async_get_pipeline(self.hass, pipeline_id)
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
        self._pipeline_ended_event.clear()
        self.hass.async_create_background_task(
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
                pipeline_id=pipeline_id,
                audio_settings=assist_pipeline.AudioSettings(
                    noise_suppression_level=self.device.noise_suppression_level,
                    auto_gain_dbfs=self.device.auto_gain,
                    volume_multiplier=self.device.volume_multiplier,
                ),
                device_id=self.device.device_id,
            ),
            name="wyoming satellite pipeline",
        )

    async def _send_delayed_ping(self) -> None:
        """Send ping to satellite after a delay."""
        assert self._client is not None

        try:
            await asyncio.sleep(_PING_SEND_DELAY)
            await self._client.write_event(Ping().event())
        except ConnectionError:
            pass  # handled with timeout

    def _event_callback(self, event: assist_pipeline.PipelineEvent) -> None:
        """Translate pipeline events into Wyoming events."""
        assert self._client is not None

        if event.type == assist_pipeline.PipelineEventType.RUN_END:
            # Pipeline run is complete
            self._is_pipeline_running = False
            self._pipeline_ended_event.set()
            self.device.set_is_active(False)
        elif event.type == assist_pipeline.PipelineEventType.WAKE_WORD_START:
            self.hass.add_job(self._client.write_event(Detect().event()))
        elif event.type == assist_pipeline.PipelineEventType.WAKE_WORD_END:
            # Wake word detection
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
            self.device.set_is_active(True)

            if event.data:
                self.hass.add_job(
                    self._client.write_event(
                        Transcribe(language=event.data["metadata"]["language"]).event()
                    )
                )
        elif event.type == assist_pipeline.PipelineEventType.STT_VAD_START:
            # User started speaking
            if event.data:
                self.hass.add_job(
                    self._client.write_event(
                        VoiceStarted(timestamp=event.data["timestamp"]).event()
                    )
                )
        elif event.type == assist_pipeline.PipelineEventType.STT_VAD_END:
            # User stopped speaking
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
                                name=event.data.get("voice"),
                                language=event.data.get("language"),
                            ),
                        ).event()
                    )
                )
        elif event.type == assist_pipeline.PipelineEventType.TTS_END:
            # TTS stream
            if event.data and (tts_output := event.data["tts_output"]):
                media_id = tts_output["media_id"]
                self.hass.add_job(self._stream_tts(media_id))
        elif event.type == assist_pipeline.PipelineEventType.ERROR:
            # Pipeline error
            if event.data:
                self.hass.add_job(
                    self._client.write_event(
                        Error(
                            text=event.data["message"], code=event.data["code"]
                        ).event()
                    )
                )

    async def _connect(self) -> None:
        """Connect to satellite over TCP."""
        await self._disconnect()

        _LOGGER.debug(
            "Connecting to satellite at %s:%s", self.service.host, self.service.port
        )
        self._client = AsyncTcpClient(self.service.host, self.service.port)
        await self._client.connect()

    async def _disconnect(self) -> None:
        """Disconnect if satellite is currently connected."""
        if self._client is None:
            return

        _LOGGER.debug("Disconnecting from satellite")
        await self._client.disconnect()
        self._client = None

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
        try:
            is_first_chunk = True
            while chunk := await self._audio_queue.get():
                if is_first_chunk:
                    is_first_chunk = False
                    _LOGGER.debug("Receiving audio from satellite")

                yield chunk
        except asyncio.CancelledError:
            pass  # ignore
