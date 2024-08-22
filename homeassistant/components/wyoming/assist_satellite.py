"""Support for Wyoming satellite services."""

import asyncio
from collections import defaultdict, deque
import io
import logging
import time
from typing import Final
import wave

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.ping import Ping, Pong
from wyoming.pipeline import PipelineStage, RunPipeline
from wyoming.satellite import PauseSatellite, RunSatellite
from wyoming.snd import Played
from wyoming.timer import TimerCancelled, TimerFinished, TimerStarted, TimerUpdated
from wyoming.tts import Synthesize, SynthesizeVoice
from wyoming.vad import VoiceStarted, VoiceStopped
from wyoming.wake import Detect, Detection

from homeassistant.components import assist_pipeline, assist_satellite, intent, tts
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.async_ import queue_to_iterable

from .const import DOMAIN
from .data import WyomingService
from .devices import SatelliteDevice
from .entity import WyomingEntity
from .models import DomainDataItem

_LOGGER = logging.getLogger(__name__)

_SAMPLES_PER_CHUNK: Final = 1024
_RECONNECT_SECONDS: Final = 10
_RESTART_SECONDS: Final = 3
_PING_TIMEOUT: Final = 5
_PING_SEND_DELAY: Final = 2
_PIPELINE_FINISH_TIMEOUT: Final = 1
_STOP_CHUNK: Final = b""

# Wyoming stage -> Assist stage
_ASSIST_STAGES: dict[PipelineStage, assist_pipeline.PipelineStage] = {
    PipelineStage.WAKE: assist_pipeline.PipelineStage.WAKE_WORD,
    PipelineStage.ASR: assist_pipeline.PipelineStage.STT,
    PipelineStage.HANDLE: assist_pipeline.PipelineStage.INTENT,
    PipelineStage.TTS: assist_pipeline.PipelineStage.TTS,
}
_WYOMING_STAGES: dict[assist_pipeline.PipelineStage, PipelineStage] = {
    assist_pipeline.PipelineStage.WAKE_WORD: PipelineStage.WAKE,
    assist_pipeline.PipelineStage.STT: PipelineStage.ASR,
    assist_pipeline.PipelineStage.INTENT: PipelineStage.HANDLE,
    assist_pipeline.PipelineStage.TTS: PipelineStage.TTS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP Assist satellite entity."""
    domain_data: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    assert domain_data.satellite_device is not None

    async_add_entities(
        [
            WyomingSatellite(
                hass, config_entry, domain_data.service, domain_data.satellite_device
            )
        ]
    )


class WyomingSatellite(WyomingEntity, assist_satellite.AssistSatelliteEntity):
    """Remote voice satellite running the Wyoming protocol."""

    _attr_supported_features = (
        assist_satellite.AssistSatelliteEntityFeature.TRIGGER_PIPELINE
    )

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        service: WyomingService,
        device: SatelliteDevice,
    ) -> None:
        """Initialize satellite."""
        WyomingEntity.__init__(self, device)
        assist_satellite.AssistSatelliteEntity.__init__(self)

        self.hass = hass
        self.config_entry = config_entry
        self.service = service
        self.device = device
        self.is_running = True

        self._client: AsyncTcpClient | None = None
        self._chunk_converter = AudioChunkConverter(
            rate=assist_pipeline.SAMPLE_RATE,
            width=assist_pipeline.SAMPLE_WIDTH,
            channels=assist_pipeline.SAMPLE_CHANNELS,
        )
        self._is_pipeline_running = False
        self._pipeline_ended_event = asyncio.Event()
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._muted_changed_event = asyncio.Event()

        # Results of remotely triggered pipelines
        self._pipeline_result_futures: dict[
            assist_pipeline.PipelineStage, deque[asyncio.Future]
        ] = defaultdict(deque)
        self._played_timeout_id: int | None = None

        self.device.set_is_muted_listener(self._muted_changed)
        self.device.set_pipeline_listener(self._pipeline_changed)
        self.device.set_audio_settings_listener(self._audio_settings_changed)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.config_entry.async_create_background_task(
            self.hass, self.run(), "wyoming_satellite_run"
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self.stop()

    async def async_trigger_pipeline_on_satellite(
        self,
        start_stage: assist_pipeline.PipelineStage,
        end_stage: assist_pipeline.PipelineStage,
        run_config: assist_satellite.PipelineRunConfig,
    ) -> assist_satellite.PipelineRunResult | None:
        """Run a pipeline on the satellite from start to end stage."""
        if self._client is None:
            return None  # not connected

        result_future: asyncio.Future[str | None] = asyncio.Future()
        self._pipeline_result_futures[start_stage].append(result_future)

        await self._client.write_event(
            RunPipeline(
                start_stage=_WYOMING_STAGES[start_stage],
                end_stage=_WYOMING_STAGES[end_stage],
                wake_word_names=run_config.wake_word_names,
                announce_text=run_config.announce_text,
            ).event()
        )

        # Wait for result
        result = await result_future
        if start_stage == assist_pipeline.PipelineStage.WAKE_WORD:
            return assist_satellite.PipelineRunResult(detected_wake_word=result)

        if start_stage == assist_pipeline.PipelineStage.STT:
            return assist_satellite.PipelineRunResult(command_text=result)

        return None

    def on_pipeline_event(self, event: assist_pipeline.PipelineEvent) -> None:
        """Translate pipeline events into Wyoming events."""
        super().on_pipeline_event(event)

        if self._client is None:
            return  # stopping

        if event.type == assist_pipeline.PipelineEventType.RUN_END:
            # Pipeline run is complete
            self._is_pipeline_running = False
            self._pipeline_ended_event.set()
            self.device.set_is_active(False)
        elif event.type == assist_pipeline.PipelineEventType.WAKE_WORD_START:
            self.hass.add_job(self._client.write_event(Detect().event()))
        elif event.type == assist_pipeline.PipelineEventType.WAKE_WORD_END:
            # Wake word detection
            # Inform client of wake word detection
            if event.data and (wake_word_output := event.data.get("wake_word_output")):
                detected_wake_word = wake_word_output["wake_word_id"]
                detection = Detection(
                    name=detected_wake_word,
                    timestamp=wake_word_output.get("timestamp"),
                )
                self.hass.add_job(self._client.write_event(detection.event()))

                # Set result for remote pipeline trigger
                if result_futures := self._pipeline_result_futures[
                    assist_pipeline.PipelineStage.WAKE_WORD
                ]:
                    result_futures.popleft().set_result(detected_wake_word)
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

                # Set result for remote pipeline trigger
                if result_futures := self._pipeline_result_futures[
                    assist_pipeline.PipelineStage.STT
                ]:
                    result_futures.popleft().set_result(stt_text)
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

    # -------------------------------------------------------------------------

    async def run(self) -> None:
        """Run and maintain a connection to satellite."""
        _LOGGER.debug("Running satellite task")

        unregister_timer_handler = intent.async_register_timer_handler(
            self.hass, self.device.device_id, self._handle_timer
        )

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
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("%s: %s", err.__class__.__name__, str(err))

                    # Ensure sensor is off (before restart)
                    self.device.set_is_active(False)

                    # Wait to restart
                    await self.on_restart()
        finally:
            unregister_timer_handler()

            # Ensure sensor is off (before stop)
            self.device.set_is_active(False)

            await self.on_stopped()

    def stop(self) -> None:
        """Signal satellite task to stop running."""
        # Cancel any running pipeline
        self._audio_queue.put_nowait(_STOP_CHUNK)

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
            self.config_entry.async_create_background_task(
                self.hass,
                self._client.write_event(PauseSatellite().event()),
                "pause satellite",
            )

    def _muted_changed(self) -> None:
        """Run when device muted status changes."""
        if self.device.is_muted:
            # Cancel any running pipeline
            self._audio_queue.put_nowait(_STOP_CHUNK)

            # Send pause event so satellite can react immediately
            self._send_pause()

        self._muted_changed_event.set()
        self._muted_changed_event.clear()

    def _pipeline_changed(self) -> None:
        """Run when device pipeline changes."""

        # Cancel any running pipeline
        self._audio_queue.put_nowait(_STOP_CHUNK)

    def _audio_settings_changed(self) -> None:
        """Run when device audio settings."""

        # Cancel any running pipeline
        self._audio_queue.put_nowait(_STOP_CHUNK)

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
        if self._client is None:
            return  # stopping

        client_info: Info | None = None
        wake_word_phrase: str | None = None
        run_pipeline: RunPipeline | None = None
        send_ping = True

        # Read events and check for pipeline end in parallel
        pipeline_ended_task = self.config_entry.async_create_background_task(
            self.hass, self._pipeline_ended_event.wait(), "satellite pipeline ended"
        )
        client_event_task = self.config_entry.async_create_background_task(
            self.hass, self._client.read_event(), "satellite event read"
        )
        pending = {pipeline_ended_task, client_event_task}

        # Update info from satellite
        await self._client.write_event(Describe().event())

        while self.is_running and (not self.device.is_muted):
            if send_ping:
                # Ensure satellite is still connected
                send_ping = False
                self.config_entry.async_create_background_task(
                    self.hass, self._send_delayed_ping(), "ping satellite"
                )

            async with asyncio.timeout(_PING_TIMEOUT):
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                if pipeline_ended_task in done:
                    # Pipeline run end event was received
                    _LOGGER.debug("Pipeline finished")
                    self._pipeline_ended_event.clear()
                    pipeline_ended_task = (
                        self.config_entry.async_create_background_task(
                            self.hass,
                            self._pipeline_ended_event.wait(),
                            "satellite pipeline ended",
                        )
                    )
                    pending.add(pipeline_ended_task)

                    # Clear last wake word detection
                    wake_word_phrase = None

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
                    self._run_pipeline_once(run_pipeline, wake_word_phrase)
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
                    self._audio_queue.put_nowait(_STOP_CHUNK)
                elif Info.is_type(client_event.type):
                    client_info = Info.from_event(client_event)
                    _LOGGER.debug("Updated client info: %s", client_info)
                elif Detection.is_type(client_event.type):
                    detection = Detection.from_event(client_event)
                    wake_word_phrase = detection.name

                    # Resolve wake word name/id to phrase if info is available.
                    #
                    # This allows us to deconflict multiple satellite wake-ups
                    # with the same wake word.
                    if (client_info is not None) and (client_info.wake is not None):
                        found_phrase = False
                        for wake_service in client_info.wake:
                            for wake_model in wake_service.models:
                                if wake_model.name == detection.name:
                                    wake_word_phrase = (
                                        wake_model.phrase or wake_model.name
                                    )
                                    found_phrase = True
                                    break

                            if found_phrase:
                                break

                    if result_futures := self._pipeline_result_futures[
                        assist_pipeline.PipelineStage.WAKE_WORD
                    ]:
                        result_futures.popleft().set_result(wake_word_phrase)

                    _LOGGER.debug("Client detected wake word: %s", wake_word_phrase)
                elif Played.is_type(client_event.type):
                    # Set result for remote pipeline trigger
                    self._played_timeout_id = None
                    if result_futures := self._pipeline_result_futures[
                        assist_pipeline.PipelineStage.TTS
                    ]:
                        result_futures.popleft().set_result(None)
                else:
                    _LOGGER.debug("Unexpected event from satellite: %s", client_event)

                # Next event
                client_event_task = self.config_entry.async_create_background_task(
                    self.hass, self._client.read_event(), "satellite event read"
                )
                pending.add(client_event_task)

    def _run_pipeline_once(
        self, run_pipeline: RunPipeline, wake_word_phrase: str | None = None
    ) -> None:
        """Run a pipeline once."""
        _LOGGER.debug("Received run information: %s", run_pipeline)

        start_stage = _ASSIST_STAGES.get(run_pipeline.start_stage)
        end_stage = _ASSIST_STAGES.get(run_pipeline.end_stage)

        if start_stage is None:
            raise ValueError(f"Invalid start stage: {start_stage}")

        if end_stage is None:
            raise ValueError(f"Invalid end stage: {end_stage}")

        # We will push audio in through a queue
        self._audio_queue = asyncio.Queue()

        # Start pipeline running
        self._is_pipeline_running = True
        self._pipeline_ended_event.clear()
        self.config_entry.async_create_background_task(
            self.hass,
            self._async_accept_pipeline_from_satellite(
                queue_to_iterable(self._audio_queue),
                start_stage,
                end_stage,
                pipeline_entity_id=self.device.get_pipeline_entity_id(self.hass),
                vad_sensitivity_entity_id=self.device.get_vad_sensitivity_entity_id(
                    self.hass
                ),
                wake_word_phrase=wake_word_phrase,
                tts_input=run_pipeline.announce_text,
            ),
            name="wyoming satellite pipeline",
        )

    async def _send_delayed_ping(self) -> None:
        """Send ping to satellite after a delay."""
        if self._client is None:
            return  # stopping

        try:
            await asyncio.sleep(_PING_SEND_DELAY)
            await self._client.write_event(Ping().event())
        except ConnectionError:
            pass  # handled with timeout

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
        try:
            if self._client is None:
                return  # stopping

            extension, data = await tts.async_get_media_source_audio(
                self.hass, media_id
            )
            if extension != "wav":
                raise ValueError(
                    f"Cannot stream audio format to satellite: {extension}"
                )

            with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                sample_channels = wav_file.getnchannels()
                num_frames = wav_file.getnframes()
                _LOGGER.debug("Streaming %s TTS sample(s)", num_frames)

                wav_seconds = num_frames / sample_rate
                self._played_timeout_id = time.monotonic_ns()
                self.config_entry.async_create_background_task(
                    self.hass,
                    self._tts_played_timeout(self._played_timeout_id, wav_seconds + 1),
                    "wyoming tts timeout",
                )

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
        finally:
            self.tts_response_finished()

    async def _tts_played_timeout(self, timeout_id: int, timeout_sec: float) -> None:
        """Set pipeline result after timeout if Played message is not received."""
        await asyncio.sleep(timeout_sec)
        if self._played_timeout_id != timeout_id:
            return

        if result_futures := self._pipeline_result_futures[
            assist_pipeline.PipelineStage.TTS
        ]:
            result_futures.popleft().set_result(None)

    @callback
    def _handle_timer(
        self, event_type: intent.TimerEventType, timer: intent.TimerInfo
    ) -> None:
        """Forward timer events to satellite."""
        if self._client is None:
            return  # stopping

        _LOGGER.debug("Timer event: type=%s, info=%s", event_type, timer)
        event: Event | None = None
        if event_type == intent.TimerEventType.STARTED:
            event = TimerStarted(
                id=timer.id,
                total_seconds=timer.seconds,
                name=timer.name,
                start_hours=timer.start_hours,
                start_minutes=timer.start_minutes,
                start_seconds=timer.start_seconds,
            ).event()
        elif event_type == intent.TimerEventType.UPDATED:
            event = TimerUpdated(
                id=timer.id,
                is_active=timer.is_active,
                total_seconds=timer.seconds,
            ).event()
        elif event_type == intent.TimerEventType.CANCELLED:
            event = TimerCancelled(id=timer.id).event()
        elif event_type == intent.TimerEventType.FINISHED:
            event = TimerFinished(id=timer.id).event()

        if event is not None:
            # Send timer event to satellite
            self.config_entry.async_create_background_task(
                self.hass, self._client.write_event(event), "wyoming timer event"
            )
