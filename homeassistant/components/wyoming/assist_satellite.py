"""Assist satellite entity for Wyoming integration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import io
import logging
import time
from typing import Any, Final
import wave

from hassil import Intents, recognize
from hassil.expression import Expression, ListReference, Sequence
from hassil.intents import WildcardSlotList
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

from homeassistant.components import assist_pipeline, ffmpeg, intent, media_source, tts
from homeassistant.components.assist_pipeline import (
    PipelineEvent,
    PipelineEventType,
    async_get_pipeline,
)
from homeassistant.components.assist_satellite import (
    AssistSatelliteAnnouncement,
    AssistSatelliteAnswer,
    AssistSatelliteConfiguration,
    AssistSatelliteEntity,
    AssistSatelliteEntityDescription,
    AssistSatelliteEntityFeature,
)
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.ulid import ulid_now

from .const import DOMAIN, SAMPLE_CHANNELS, SAMPLE_WIDTH
from .data import WyomingService
from .devices import SatelliteDevice
from .entity import WyomingSatelliteEntity
from .models import DomainDataItem

_LOGGER = logging.getLogger(__name__)

_SAMPLES_PER_CHUNK: Final = 1024
_RECONNECT_SECONDS: Final = 10
_RESTART_SECONDS: Final = 3
_PING_TIMEOUT: Final = 5
_PING_SEND_DELAY: Final = 2
_PIPELINE_FINISH_TIMEOUT: Final = 1
_TTS_SAMPLE_RATE: Final = 16000
_ANNOUNCE_CHUNK_BYTES: Final = 2048
_TTS_TIMEOUT_EXTRA: Final = 1.0

_STAGES: dict[PipelineStage, assist_pipeline.PipelineStage] = {
    PipelineStage.WAKE: assist_pipeline.PipelineStage.WAKE_WORD,
    PipelineStage.ASR: assist_pipeline.PipelineStage.STT,
    PipelineStage.HANDLE: assist_pipeline.PipelineStage.INTENT,
    PipelineStage.TTS: assist_pipeline.PipelineStage.TTS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wyoming Assist satellite entity."""
    domain_data: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    assert domain_data.device is not None
    async_add_entities(
        [
            WyomingAssistSatellite(
                hass, domain_data.service, domain_data.device, config_entry
            )
        ]
    )


class WyomingAssistSatellite(WyomingSatelliteEntity, AssistSatelliteEntity):
    """Assist satellite for Wyoming devices."""

    entity_description = AssistSatelliteEntityDescription(key="assist_satellite")
    _attr_translation_key = "assist_satellite"
    _attr_name = None
    _attr_supported_features = (
        AssistSatelliteEntityFeature.ANNOUNCE
        | AssistSatelliteEntityFeature.START_CONVERSATION
    )

    def __init__(
        self,
        hass: HomeAssistant,
        service: WyomingService,
        device: SatelliteDevice,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize an Assist satellite."""
        WyomingSatelliteEntity.__init__(self, device)
        AssistSatelliteEntity.__init__(self)
        self.service = service
        self.device = device
        self.config_entry = config_entry
        self.is_running = True
        self._client: AsyncTcpClient | None = None
        self._chunk_converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self._is_pipeline_running = False
        self._pipeline_ended_event = asyncio.Event()
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._pipeline_id: str | None = None
        self._muted_changed_event = asyncio.Event()
        self._conversation_id: str | None = None
        self._conversation_id_time: float | None = None
        self.device.set_is_muted_listener(self._muted_changed)
        self.device.set_pipeline_listener(self._pipeline_changed)
        self.device.set_audio_settings_listener(self._audio_settings_changed)
        self._ffmpeg_manager: ffmpeg.FFmpegManager | None = None
        self._played_event_received: asyncio.Event | None = None
        self._run_loop_id: str | None = None
        self._tts_stream_token: str | None = None
        self._is_tts_streaming: bool = False
        self._is_asking_question: bool = False
        self._stt_future: asyncio.Future[str | None] | None = None

    @property
    def pipeline_entity_id(self) -> str | None:
        """Return the entity ID of the pipeline to use."""
        return self.device.get_pipeline_entity_id(self.hass)

    @property
    def vad_sensitivity_entity_id(self) -> str | None:
        """Return the entity ID of the VAD sensitivity to use."""
        return self.device.get_vad_sensitivity_entity_id(self.hass)

    @property
    def tts_options(self) -> dict[str, Any] | None:
        """Return options for text-to-speech."""
        return {
            tts.ATTR_PREFERRED_FORMAT: "wav",
            tts.ATTR_PREFERRED_SAMPLE_RATE: _TTS_SAMPLE_RATE,
            tts.ATTR_PREFERRED_SAMPLE_CHANNELS: SAMPLE_CHANNELS,
            tts.ATTR_PREFERRED_SAMPLE_BYTES: SAMPLE_WIDTH,
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.start_satellite()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self.stop_satellite()

    @callback
    def async_get_configuration(self) -> AssistSatelliteConfiguration:
        """Get the satellite's configuration."""
        raise NotImplementedError

    async def async_set_configuration(
        self, config: AssistSatelliteConfiguration
    ) -> None:
        """Set the satellite's configuration."""
        raise NotImplementedError

    def _get_wyoming_event(self, event: PipelineEvent) -> Event | None:
        """Get a Wyoming event from a pipeline event."""
        if event.type == assist_pipeline.PipelineEventType.WAKE_WORD_START:
            return Detect().event()

        if event.type == assist_pipeline.PipelineEventType.WAKE_WORD_END:
            if event.data and (wake_word_output := event.data.get("wake_word_output")):
                return Detection(
                    name=wake_word_output["wake_word_id"],
                    timestamp=wake_word_output.get("timestamp"),
                ).event()

        elif event.type == assist_pipeline.PipelineEventType.STT_START:
            if event.data:
                return Transcribe(language=event.data["metadata"]["language"]).event()

        elif event.type == assist_pipeline.PipelineEventType.STT_VAD_START:
            if event.data:
                return VoiceStarted(timestamp=event.data["timestamp"]).event()

        elif event.type == assist_pipeline.PipelineEventType.STT_VAD_END:
            if event.data:
                return VoiceStopped(timestamp=event.data["timestamp"]).event()

        elif event.type == assist_pipeline.PipelineEventType.STT_END:
            if event.data:
                return Transcript(text=event.data["stt_output"]["text"]).event()

        elif event.type == assist_pipeline.PipelineEventType.TTS_START:
            if event.data:
                return Synthesize(
                    text=event.data["tts_input"],
                    voice=SynthesizeVoice(
                        name=event.data.get("voice"),
                        language=event.data.get("language"),
                    ),
                ).event()

        elif event.type == assist_pipeline.PipelineEventType.ERROR:
            if event.data:
                return Error(
                    text=event.data["message"], code=event.data["code"]
                ).event()

        return None

    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Handle events from the pipeline and forward them to the satellite."""
        assert self._client is not None

        # Handle events that require special logic
        if self._stt_future and not self._stt_future.done():
            if event.type == PipelineEventType.STT_END:
                stt_text = (
                    event.data.get("stt_output", {}).get("text") if event.data else None
                )
                self._stt_future.set_result(stt_text)
            elif event.type in (PipelineEventType.RUN_END, PipelineEventType.ERROR):
                self._stt_future.set_result(None)

        if event.type == assist_pipeline.PipelineEventType.RUN_START:
            if event.data and (tts_output := event.data.get("tts_output")):
                self._tts_stream_token = tts_output["token"]
                self._is_tts_streaming = False
            return  # Do not forward

        if event.type == assist_pipeline.PipelineEventType.RUN_END:
            self._is_pipeline_running = False
            self._pipeline_ended_event.set()
            self.device.set_is_active(False)
            self._tts_stream_token = None
            self._is_tts_streaming = False
            return  # Do not forward

        if event.type == assist_pipeline.PipelineEventType.INTENT_PROGRESS:
            if (
                event.data
                and event.data.get("tts_start_streaming")
                and self._tts_stream_token
                and (stream := tts.async_get_stream(self.hass, self._tts_stream_token))
            ):
                self._is_tts_streaming = True
                self.config_entry.async_create_background_task(
                    self.hass,
                    self._stream_tts(stream),
                    f"{self.entity_id} {event.type}",
                )
            return  # Do not forward

        if event.type == assist_pipeline.PipelineEventType.TTS_END:
            if (
                event.data
                and (tts_output := event.data.get("tts_output"))
                and not self._is_tts_streaming
                and (stream := tts.async_get_stream(self.hass, tts_output["token"]))
            ):
                self.config_entry.async_create_background_task(
                    self.hass,
                    self._stream_tts(stream),
                    f"{self.entity_id} {event.type}",
                )
            return  # Do not forward

        # Use the helper for all other standard event mappings
        if wyoming_event := self._get_wyoming_event(event):
            self.config_entry.async_create_background_task(
                self.hass,
                self._client.write_event(wyoming_event),
                f"{self.entity_id} {event.type}",
            )

    async def _play_media(self, media_url: str) -> None:
        """Play audio from a URL by streaming it to the satellite via ffmpeg."""
        assert self._client is not None
        if self._ffmpeg_manager is None:
            self._ffmpeg_manager = ffmpeg.get_ffmpeg_manager(self.hass)
        if self._played_event_received is None:
            self._played_event_received = asyncio.Event()

        self._played_event_received.clear()

        await self._client.write_event(
            AudioStart(
                rate=_TTS_SAMPLE_RATE,
                width=SAMPLE_WIDTH,
                channels=SAMPLE_CHANNELS,
                timestamp=0,
            ).event()
        )

        timestamp = 0
        try:
            proc = await asyncio.create_subprocess_exec(
                self._ffmpeg_manager.binary,
                "-i",
                media_url,
                "-f",
                "s16le",
                "-ac",
                str(SAMPLE_CHANNELS),
                "-ar",
                str(_TTS_SAMPLE_RATE),
                "-nostats",
                "pipe:",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                close_fds=False,
            )
            assert proc.stdout is not None

            while True:
                chunk_bytes = await proc.stdout.read(_ANNOUNCE_CHUNK_BYTES)
                if not chunk_bytes:
                    break
                chunk = AudioChunk(
                    rate=_TTS_SAMPLE_RATE,
                    width=SAMPLE_WIDTH,
                    channels=SAMPLE_CHANNELS,
                    audio=chunk_bytes,
                    timestamp=timestamp,
                )
                await self._client.write_event(chunk.event())
                timestamp += chunk.milliseconds

        finally:
            await self._client.write_event(AudioStop().event())
            if timestamp > 0:
                audio_seconds = timestamp / 1000
                try:
                    async with asyncio.timeout(audio_seconds + 1.5):
                        await self._played_event_received.wait()
                except TimeoutError:
                    _LOGGER.debug("Did not receive played event for announcement")

    async def async_announce(self, announcement: AssistSatelliteAnnouncement) -> None:
        """Announce media on the satellite."""
        await self._play_media(announcement.media_id)

    async def async_start_conversation(
        self, start_announcement: AssistSatelliteAnnouncement
    ) -> None:
        """Start a conversation from the satellite by playing an announcement and then listening."""
        if start_announcement.preannounce_media_id:
            await self._play_media(start_announcement.preannounce_media_id)

        await self._play_media(start_announcement.media_id)

        if self._client is None:
            _LOGGER.warning("Not connected to satellite for start_conversation")
            return

        assert self._client is not None
        await self._client.write_event(Detection(name="command_start").event())

    def start_satellite(self) -> None:
        """Start the main satellite event loop."""
        self.is_running = True
        self.config_entry.async_create_background_task(
            self.hass, self.run(), "wyoming satellite run"
        )

    def stop_satellite(self) -> None:
        """Stop the main satellite event loop."""
        self._audio_queue.put_nowait(None)
        self._send_pause()
        self.is_running = False
        self._muted_changed_event.set()

    async def run(self) -> None:
        """Run the main satellite event loop, reconnecting on failure."""
        unregister_timer_handler = intent.async_register_timer_handler(
            self.hass, self.device.device_id, self._handle_timer
        )
        try:
            while self.is_running:
                try:
                    while self.device.is_muted:
                        await self.on_muted()
                        if not self.is_running:
                            return
                    await self._connect_and_loop()
                except asyncio.CancelledError:
                    raise
                except (TimeoutError, ConnectionError) as err:
                    _LOGGER.debug("%s: %s", err.__class__.__name__, str(err))
                    self._audio_queue.put_nowait(None)
                    self.device.set_is_active(False)
                    await self.on_restart()
        finally:
            unregister_timer_handler()
            self.device.set_is_active(False)
            await self.on_stopped()

    async def on_restart(self) -> None:
        """Handle disconnection and schedule a restart."""
        _LOGGER.warning(
            "Satellite has been disconnected. Reconnecting in %s second(s)",
            _RECONNECT_SECONDS,
        )
        await asyncio.sleep(_RESTART_SECONDS)

    async def on_reconnect(self) -> None:
        """Handle a failed connection attempt and schedule a retry."""
        _LOGGER.debug(
            "Failed to connect to satellite. Reconnecting in %s second(s)",
            _RECONNECT_SECONDS,
        )
        await asyncio.sleep(_RECONNECT_SECONDS)

    async def on_muted(self) -> None:
        """Wait until the satellite is unmuted."""
        await self._muted_changed_event.wait()

    async def on_stopped(self) -> None:
        """Log that the satellite task has been stopped."""
        _LOGGER.debug("Satellite task stopped")

    def _send_pause(self) -> None:
        if self._client is not None:
            self.config_entry.async_create_background_task(
                self.hass,
                self._client.write_event(PauseSatellite().event()),
                "pause satellite",
            )

    def _muted_changed(self) -> None:
        if self.device.is_muted:
            self._audio_queue.put_nowait(None)
            self._send_pause()
        self._muted_changed_event.set()
        self._muted_changed_event.clear()

    def _pipeline_changed(self) -> None:
        self._audio_queue.put_nowait(None)

    def _audio_settings_changed(self) -> None:
        self._audio_queue.put_nowait(None)

    async def _connect_and_loop(self) -> None:
        while self.is_running and (not self.device.is_muted):
            try:
                await self._connect()
                break
            except ConnectionError:
                self._client = None
                await self.on_reconnect()
        if self._client is None:
            return
        await self._client.write_event(RunSatellite().event())
        while self.is_running and (not self.device.is_muted):
            await self._run_pipeline_loop()

    async def _run_pipeline_loop(self) -> None:
        assert self._client is not None
        client_info: Info | None = None
        wake_word_phrase: str | None = None
        run_pipeline: RunPipeline | None = None
        send_ping = True
        self._run_loop_id = ulid_now()
        pipeline_ended_task = self.config_entry.async_create_background_task(
            self.hass, self._pipeline_ended_event.wait(), "satellite pipeline ended"
        )
        client_event_task = self.config_entry.async_create_background_task(
            self.hass, self._client.read_event(), "satellite event read"
        )
        pending = {pipeline_ended_task, client_event_task}
        await self._client.write_event(Describe().event())
        while self.is_running and (not self.device.is_muted):
            if send_ping:
                send_ping = False
                self.config_entry.async_create_background_task(
                    self.hass, self._send_delayed_ping(), "ping satellite"
                )
            async with asyncio.timeout(_PING_TIMEOUT):
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                if pipeline_ended_task in done:
                    self._pipeline_ended_event.clear()
                    pipeline_ended_task = (
                        self.config_entry.async_create_background_task(
                            self.hass,
                            self._pipeline_ended_event.wait(),
                            "satellite pipeline ended",
                        )
                    )
                    pending.add(pipeline_ended_task)
                    wake_word_phrase = None
                    if (run_pipeline is not None) and run_pipeline.restart_on_end:
                        self._run_pipeline_once(run_pipeline)
                        continue
                if client_event_task not in done:
                    continue
                client_event = client_event_task.result()
                if client_event is None:
                    raise ConnectionResetError("Satellite disconnected")
                if Pong.is_type(client_event.type):
                    send_ping = True
                elif Ping.is_type(client_event.type):
                    ping = Ping.from_event(client_event)
                    await self._client.write_event(Pong(text=ping.text).event())
                elif RunPipeline.is_type(client_event.type):
                    run_pipeline = RunPipeline.from_event(client_event)
                    self._run_pipeline_once(run_pipeline, wake_word_phrase)
                elif (
                    AudioChunk.is_type(client_event.type) and self._is_pipeline_running
                ):
                    chunk = AudioChunk.from_event(client_event)
                    chunk = self._chunk_converter.convert(chunk)
                    self._audio_queue.put_nowait(chunk.audio)
                elif AudioStop.is_type(client_event.type) and self._is_pipeline_running:
                    self._audio_queue.put_nowait(None)
                elif Info.is_type(client_event.type):
                    client_info = Info.from_event(client_event)
                elif Detection.is_type(client_event.type):
                    detection = Detection.from_event(client_event)
                    wake_word_phrase = detection.name
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
                elif Played.is_type(client_event.type):
                    self.tts_response_finished()
                    if self._played_event_received is not None:
                        self._played_event_received.set()
                else:
                    _LOGGER.debug("Unexpected event from satellite: %s", client_event)
                client_event_task = self.config_entry.async_create_background_task(
                    self.hass, self._client.read_event(), "satellite event read"
                )
                pending.add(client_event_task)

    def _run_pipeline_once(
        self, run_pipeline: RunPipeline, wake_word_phrase: str | None = None
    ) -> None:
        start_stage = _STAGES.get(run_pipeline.start_stage)
        end_stage = _STAGES.get(run_pipeline.end_stage)

        if self._is_asking_question:
            end_stage = assist_pipeline.PipelineStage.STT

        if start_stage is None:
            raise ValueError(f"Invalid start stage: {start_stage}")
        if end_stage is None:
            raise ValueError(f"Invalid end stage: {end_stage}")
        self._audio_queue = asyncio.Queue()
        self._is_pipeline_running = True
        self._pipeline_ended_event.clear()
        self.config_entry.async_create_background_task(
            self.hass,
            self.async_accept_pipeline_from_satellite(
                audio_stream=self._stt_stream(),
                start_stage=start_stage,
                end_stage=end_stage,
                wake_word_phrase=wake_word_phrase,
            ),
            "wyoming satellite pipeline",
        )

    async def _send_delayed_ping(self) -> None:
        assert self._client is not None
        try:
            await asyncio.sleep(_PING_SEND_DELAY)
            await self._client.write_event(Ping().event())
        except ConnectionError:
            pass

    async def _connect(self) -> None:
        await self._disconnect()
        self._client = AsyncTcpClient(self.service.host, self.service.port)
        await self._client.connect()

    async def _disconnect(self) -> None:
        if self._client is None:
            return
        await self._client.disconnect()
        self._client = None

    async def _stream_tts(self, tts_result: tts.ResultStream) -> None:
        assert self._client is not None
        if tts_result.extension != "wav":
            raise ValueError(
                f"Cannot stream audio format to satellite: {tts_result.extension}"
            )
        total_seconds = 0.0
        start_time = time.monotonic()
        try:
            header_data = b""
            header_complete = False
            sample_rate: int | None = None
            sample_width: int | None = None
            sample_channels: int | None = None
            timestamp = 0
            async for data_chunk in tts_result.async_stream_result():
                if not header_complete:
                    header_data += data_chunk
                    if len(header_data) >= 44 and (
                        audio_info := _try_parse_wav_header(header_data)
                    ):
                        (
                            sample_rate,
                            sample_width,
                            sample_channels,
                            data_chunk,
                        ) = audio_info
                        await self._client.write_event(
                            AudioStart(
                                rate=sample_rate,
                                width=sample_width,
                                channels=sample_channels,
                                timestamp=timestamp,
                            ).event()
                        )
                        header_complete = True
                        if not data_chunk:
                            continue
                    else:
                        continue
                assert (
                    sample_rate is not None
                    and sample_width is not None
                    and sample_channels is not None
                )
                audio_chunk = AudioChunk(
                    rate=sample_rate,
                    width=sample_width,
                    channels=sample_channels,
                    audio=data_chunk,
                    timestamp=timestamp,
                )
                await self._client.write_event(audio_chunk.event())
                timestamp += audio_chunk.milliseconds
                total_seconds += audio_chunk.seconds
            await self._client.write_event(AudioStop(timestamp=timestamp).event())
        finally:
            send_duration = time.monotonic() - start_time
            timeout_seconds = max(0, total_seconds - send_duration + _TTS_TIMEOUT_EXTRA)
            self.config_entry.async_create_background_task(
                self.hass,
                self._tts_timeout(timeout_seconds, self._run_loop_id),
                name="wyoming TTS timeout",
            )

    async def _stt_stream(self) -> AsyncGenerator[bytes]:
        is_first_chunk = True
        while chunk := await self._audio_queue.get():
            if chunk is None:
                break
            if is_first_chunk:
                is_first_chunk = False
            yield chunk

    async def _tts_timeout(
        self, timeout_seconds: float, run_loop_id: str | None
    ) -> None:
        await asyncio.sleep(timeout_seconds + _TTS_TIMEOUT_EXTRA)
        if run_loop_id != self._run_loop_id:
            return
        self.tts_response_finished()

    @callback
    def _handle_timer(
        self, event_type: intent.TimerEventType, timer: intent.TimerInfo
    ) -> None:
        assert self._client is not None
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
                id=timer.id, is_active=timer.is_active, total_seconds=timer.seconds
            ).event()
        elif event_type == intent.TimerEventType.CANCELLED:
            event = TimerCancelled(id=timer.id).event()
        elif event_type == intent.TimerEventType.FINISHED:
            event = TimerFinished(id=timer.id).event()
        if event is not None:
            self.config_entry.async_create_background_task(
                self.hass, self._client.write_event(event), "wyoming timer event"
            )

    def _collect_list_references(
        self, expression: Expression, list_names: set[str]
    ) -> None:
        """Collect list reference names recursively."""
        if isinstance(expression, Sequence):
            seq: Sequence = expression
            for item in seq.items:
                self._collect_list_references(item, list_names)
        elif isinstance(expression, ListReference):
            # {list}
            list_ref: ListReference = expression
            list_names.add(list_ref.slot_name)

    def _question_response_to_answer(
        self, response_text: str, answers: list[dict[str, Any]]
    ) -> AssistSatelliteAnswer:
        """Match text to a pre-defined set of answers."""
        intents = Intents.from_dict(
            {
                "language": self.hass.config.language,
                "intents": {
                    "QuestionIntent": {
                        "data": [
                            {
                                "sentences": answer["sentences"],
                                "metadata": {"answer_id": answer["id"]},
                            }
                            for answer in answers
                        ]
                    }
                },
            }
        )

        wildcard_names: set[str] = set()
        for intent_obj in intents.intents.values():
            for intent_data in intent_obj.data:
                for sentence in intent_data.sentences:
                    self._collect_list_references(sentence, wildcard_names)  # type: ignore[arg-type]

        for wildcard_name in wildcard_names:
            intents.slot_lists[wildcard_name] = WildcardSlotList(wildcard_name)

        result = recognize(response_text, intents)
        if result is None:
            return AssistSatelliteAnswer(id=None, sentence=response_text)

        assert result.intent_metadata
        return AssistSatelliteAnswer(
            id=result.intent_metadata["answer_id"],
            sentence=response_text,
            slots={
                entity_name: entity.value
                for entity_name, entity in result.entities.items()
            },
        )

    async def _resolve_announcement_media_id(
        self,
        message: str,
        media_id: str | None,
        preannounce_media_id: str | None = None,
    ) -> AssistSatelliteAnnouncement:
        """Resolve the media ID."""

        media_id_source: str | None = None
        tts_token: str | None = None
        if media_id:
            original_media_id = media_id
        else:
            media_id_source = "tts"
            pipeline = async_get_pipeline(self.hass, self._pipeline_id)
            engine = tts.async_resolve_engine(self.hass, pipeline.tts_engine)
            if engine is None:
                raise HomeAssistantError(f"TTS engine {pipeline.tts_engine} not found")
            tts_options: dict[str, Any] = {}
            if pipeline.tts_voice is not None:
                tts_options[tts.ATTR_VOICE] = pipeline.tts_voice
            if self.tts_options is not None:
                tts_options.update(self.tts_options)
            stream = tts.async_create_stream(
                self.hass,
                engine=engine,
                language=pipeline.tts_language,
                options=tts_options,
            )
            stream.async_set_message(message)
            tts_token = stream.token
            media_id = stream.url
            original_media_id = tts.generate_media_source_id(
                self.hass,
                message,
                engine=engine,
                language=pipeline.tts_language,
                options=tts_options,
            )
        if media_source.is_media_source_id(media_id):
            if not media_id_source:
                media_id_source = "media_id"
            media = await media_source.async_resolve_media(self.hass, media_id, None)
            media_id = media.url
        if not media_id_source:
            media_id_source = "url"
        media_id = async_process_play_media_url(self.hass, media_id)
        if preannounce_media_id:
            if media_source.is_media_source_id(preannounce_media_id):
                preannounce_media = await media_source.async_resolve_media(
                    self.hass, preannounce_media_id, None
                )
                preannounce_media_id = preannounce_media.url
            preannounce_media_id = async_process_play_media_url(
                self.hass, preannounce_media_id
            )
        return AssistSatelliteAnnouncement(
            message=message,
            media_id=media_id,
            original_media_id=original_media_id,
            tts_token=tts_token,
            media_id_source=media_id_source,  # type: ignore[arg-type]
            preannounce_media_id=preannounce_media_id,
        )

    async def async_internal_ask_question(
        self,
        question: str | None = None,
        question_media_id: str | None = None,
        preannounce: bool = True,
        preannounce_media_id: str | None = None,
        answers: list[dict[str, Any]] | None = None,
    ) -> AssistSatelliteAnswer | None:
        """Ask a question and get a response, correctly handling pre-announcements."""
        self._is_asking_question = True
        self._stt_future = asyncio.Future()

        try:
            announcement = await self._resolve_announcement_media_id(
                message=question or "",
                media_id=question_media_id,
                preannounce_media_id=preannounce_media_id if preannounce else None,
            )

            if announcement.preannounce_media_id:
                await self._play_media(announcement.preannounce_media_id)

            await self._play_media(announcement.media_id)

            assert self._client is not None
            await self._client.write_event(Detection(name="command_start").event())

            stt_response = await self._stt_future

            if stt_response is None:
                return None

            if not answers:
                return AssistSatelliteAnswer(id=None, sentence=stt_response, slots={})

            return self._question_response_to_answer(stt_response, answers)

        finally:
            self._is_asking_question = False
            self._stt_future = None


def _try_parse_wav_header(header_data: bytes) -> tuple[int, int, int, bytes] | None:
    """Try to parse a WAV header from a buffer."""
    try:
        with io.BytesIO(header_data) as wav_io:
            wav_file: wave.Wave_read = wave.open(wav_io, "rb")
            with wav_file:
                return (
                    wav_file.getframerate(),
                    wav_file.getsampwidth(),
                    wav_file.getnchannels(),
                    wav_file.readframes(wav_file.getnframes()),
                )
    except wave.Error:
        pass
    return None
