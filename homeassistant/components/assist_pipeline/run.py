"""Run controller for Assist pipelines."""

import asyncio
from collections.abc import AsyncIterable
from dataclasses import dataclass, field
import logging
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import time
from typing import Any, Protocol, override
import wave

from homeassistant.components import conversation, stt
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import chat_session, llm
from homeassistant.util import ulid as ulid_util
from homeassistant.util.limited_size_dict import LimitedSizeDict

from .audio_output import AudioOutputStream, PipelineAudioOutput
from .const import (
    CONF_DEBUG_RECORDING_DIR,
    DATA_CONFIG,
    DATA_LAST_WAKE_UP,
    DOMAIN,
    SAMPLE_CHANNELS,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    WAKE_WORD_COOLDOWN,
)
from .default_pipeline import _DefaultPipelineProcessor
from .error import (
    DuplicateWakeUpDetectedError,
    InvalidPipelineStagesError,
    PipelineError,
)
from .models import (
    PIPELINE_STAGE_ORDER,
    AudioSettings,
    Pipeline,
    PipelineEvent,
    PipelineEventCallback,
    PipelineEventType,
    PipelineStage,
    WakeWordSettings,
)
from .runtime import KEY_ASSIST_PIPELINE, PipelineRunDebug
from .tool_host import PipelineToolHost

_LOGGER = logging.getLogger(__name__)

STORED_PIPELINE_RUNS = 10


class _PipelineProcessor(Protocol):
    """Implementation boundary for processing a pipeline run."""

    @property
    def response_audio(self) -> AudioOutputStream | None:
        """Return the response audio stream."""

    @property
    def supports_streaming_response(self) -> bool | None:
        """Return whether response audio can be streamed."""

    @property
    def start_response_immediately(self) -> bool:
        """Return whether response audio should be consumed at run start."""

    async def async_validate(self, request: _PipelineProcessorRequest) -> None:
        """Validate pipeline input and prepare processing resources."""

    async def async_execute(self, request: _PipelineProcessorRequest) -> None:
        """Process pipeline input."""

    def invalidate(self) -> None:
        """Invalidate active processing."""

    def cleanup(self) -> None:
        """Clean up resources after a pipeline error."""


@dataclass(frozen=True, slots=True, kw_only=True)
class _PipelineProcessorRequest:
    """Input passed across the private pipeline processor boundary."""

    session: chat_session.ChatSession
    stt_metadata: stt.SpeechMetadata | None = None
    stt_stream: AsyncIterable[bytes] | None = None
    wake_word_phrase: str | None = None
    intent_input: str | None = None
    tts_input: str | None = None
    conversation_extra_system_prompt: str | None = None
    device_id: str | None = None
    satellite_id: str | None = None


@dataclass
class PipelineRun:
    """Home Assistant controller for a pipeline run."""

    hass: HomeAssistant
    context: Context
    pipeline: Pipeline
    start_stage: PipelineStage
    end_stage: PipelineStage
    event_callback: PipelineEventCallback
    language: str = None  # type: ignore[assignment]
    runner_data: Any | None = None
    tts_audio_output: str | dict[str, Any] | None = None
    wake_word_settings: WakeWordSettings | None = None
    audio_settings: AudioSettings = field(default_factory=AudioSettings)
    llm_api_id: str | list[str] = llm.LLM_API_ASSIST

    id: str = field(default_factory=ulid_util.ulid_now)
    debug_recording_thread: Thread | None = None
    """Thread that records audio to debug_recording_dir."""
    debug_recording_queue: Queue[str | bytes | None] | None = None
    """Queue to communicate with the debug recording thread."""
    _device_id: str | None = None
    _satellite_id: str | None = None
    _processor: _PipelineProcessor = field(init=False, repr=False)
    _response_audio_outputs: list[PipelineAudioOutput] = field(
        init=False, default_factory=list, repr=False
    )
    _registered: bool = field(init=False, default=False, repr=False)
    _started: bool = field(init=False, default=False, repr=False)
    _ended: bool = field(init=False, default=False, repr=False)
    _tool_host: PipelineToolHost | None = field(init=False, default=None, repr=False)
    _tool_host_lock: asyncio.Lock = field(
        init=False, default_factory=asyncio.Lock, repr=False
    )

    def __post_init__(self) -> None:
        """Initialize the pipeline controller."""
        self.language = self.pipeline.language or self.hass.config.language

        if PIPELINE_STAGE_ORDER.index(self.end_stage) < PIPELINE_STAGE_ORDER.index(
            self.start_stage
        ):
            raise InvalidPipelineStagesError(self.start_stage, self.end_stage)

        self._processor = _create_pipeline_processor(self)
        pipeline_data = self.hass.data[KEY_ASSIST_PIPELINE]
        if self.pipeline.id not in pipeline_data.pipeline_debug:
            pipeline_data.pipeline_debug[self.pipeline.id] = LimitedSizeDict(
                size_limit=STORED_PIPELINE_RUNS
            )
        pipeline_data.pipeline_debug[self.pipeline.id][self.id] = PipelineRunDebug()
        pipeline_data.pipeline_runs.add_run(self)
        self._registered = True

    @override
    def __eq__(self, other: object) -> bool:
        """Compare pipeline runs by id."""
        if isinstance(other, PipelineRun):
            return self.id == other.id
        return False

    @property
    def device_id(self) -> str | None:
        """Return the device associated with the run."""
        return self._device_id

    @property
    def satellite_id(self) -> str | None:
        """Return the satellite associated with the run."""
        return self._satellite_id

    @callback
    def async_create_response_audio(
        self, extension: str, content_type: str
    ) -> PipelineAudioOutput:
        """Create a controller-owned response audio stream."""
        output = self.hass.data[KEY_ASSIST_PIPELINE].audio_output_manager.async_create(
            extension, content_type
        )
        self._response_audio_outputs.append(output)
        return output

    async def async_get_tool_host(self) -> PipelineToolHost:
        """Return the Home Assistant tool host for this pipeline run."""
        async with self._tool_host_lock:
            if self._tool_host is None:
                self._tool_host = await PipelineToolHost.async_create(
                    self.hass,
                    self.llm_api_id,
                    llm.LLMContext(
                        platform=DOMAIN,
                        context=self.context,
                        language=self.language,
                        assistant=conversation.DOMAIN,
                        device_id=self._device_id,
                    ),
                )
            return self._tool_host

    @callback
    def process_event(self, event: PipelineEvent) -> None:
        """Log an event and call the listener."""
        self.event_callback(event)
        pipeline_data = self.hass.data[KEY_ASSIST_PIPELINE]
        if self.id not in pipeline_data.pipeline_debug[self.pipeline.id]:
            return
        pipeline_data.pipeline_debug[self.pipeline.id][self.id].events.append(event)

    def start(
        self, conversation_id: str, device_id: str | None, satellite_id: str | None
    ) -> None:
        """Emit the run-start event."""
        if self._started:
            raise RuntimeError("Pipeline run has already started")

        self._started = True
        self._device_id = device_id
        self._satellite_id = satellite_id
        if self.start_stage in (PipelineStage.WAKE_WORD, PipelineStage.STT):
            self._start_debug_recording_thread()

        data: dict[str, Any] = {
            "pipeline": self.pipeline.id,
            "language": self.language,
            "conversation_id": conversation_id,
        }
        if satellite_id is not None:
            data["satellite_id"] = satellite_id
        if self.runner_data is not None:
            data["runner_data"] = self.runner_data
        if response_audio := self._processor.response_audio:
            tts_output = data["tts_output"] = {
                "token": response_audio.token,
                "url": response_audio.url,
                "mime_type": response_audio.content_type,
                "stream_response": self._processor.supports_streaming_response,
            }
            if self._processor.start_response_immediately:
                tts_output["start_streaming"] = True
        self.process_event(PipelineEvent(PipelineEventType.RUN_START, data))

    async def end(self) -> None:
        """Emit the run-end event."""
        if self._ended:
            return

        if not self._started:
            self._ended = True
            self._unregister()
            return

        self._ended = True
        try:
            for output in self._response_audio_outputs:
                output.async_close()
            self.capture_audio(None)
            await self._stop_debug_recording_thread()
            self.process_event(PipelineEvent(PipelineEventType.RUN_END))
        finally:
            self._unregister()

    async def async_validate(self, pipeline_input: PipelineInput) -> None:
        """Validate input and prepare the pipeline processor."""
        request = pipeline_input.create_processor_request()
        self._set_request_identity(request)
        try:
            await self._processor.async_validate(request)
        except BaseException as err:
            self._cleanup_failed_processor(err)
            self._unregister()
            raise

    async def async_execute(
        self, pipeline_input: PipelineInput, *, validate: bool = False
    ) -> None:
        """Run the pipeline processor with the Home Assistant lifecycle."""
        request = pipeline_input.create_processor_request()
        validation_error: PipelineError | None = None
        self._set_request_identity(request)

        try:
            if validate:
                try:
                    await self._processor.async_validate(request)
                except PipelineError as err:
                    validation_error = err

            self.start(
                conversation_id=request.session.conversation_id,
                device_id=request.device_id,
                satellite_id=request.satellite_id,
            )
            await self._async_process(request, validation_error)
        except PipelineError as err:
            self._cleanup_failed_processor(err)
            self.process_event(
                PipelineEvent(
                    PipelineEventType.ERROR,
                    {"code": err.code, "message": err.message},
                )
            )
        except BaseException as err:
            self._cleanup_failed_processor(err)
            raise
        finally:
            await self.end()

    async def _async_process(
        self,
        request: _PipelineProcessorRequest,
        validation_error: PipelineError | None,
    ) -> None:
        """Execute a previously validated processor request."""
        if validation_error is not None:
            raise validation_error
        await self._processor.async_execute(request)

    @callback
    def _set_request_identity(self, request: _PipelineProcessorRequest) -> None:
        """Set identity used by controller-provided processor services."""
        self._device_id = request.device_id
        self._satellite_id = request.satellite_id

    @callback
    def _cleanup_failed_processor(self, err: BaseException) -> None:
        """Fail response streams and clean up processor resources."""
        for output in self._response_audio_outputs:
            output.async_fail(err)
        self._processor.cleanup()

    @callback
    def _unregister(self) -> None:
        """Remove this run from the active run registry."""
        if self._registered:
            self.hass.data[KEY_ASSIST_PIPELINE].pipeline_runs.remove_run(self)
            self._registered = False

    @callback
    def invalidate(self) -> None:
        """Invalidate active processing for this run."""
        self._processor.invalidate()

    @callback
    def accept_wake_word(self, wake_word_phrase: str) -> None:
        """Apply Home Assistant's duplicate wake-up policy."""
        last_wake_up = self.hass.data[DATA_LAST_WAKE_UP].get(wake_word_phrase)
        if (
            last_wake_up is not None
            and (time.monotonic() - last_wake_up) < WAKE_WORD_COOLDOWN
        ):
            _LOGGER.debug("Duplicate wake-up detected for %s", wake_word_phrase)
            raise DuplicateWakeUpDetectedError(wake_word_phrase)
        self.hass.data[DATA_LAST_WAKE_UP][wake_word_phrase] = time.monotonic()

    @callback
    def capture_audio(self, audio_bytes: bytes | None) -> None:
        """Forward an audio chunk to Home Assistant capture mechanisms."""
        if self.debug_recording_queue is not None:
            self.debug_recording_queue.put_nowait(audio_bytes)

        if self._device_id is None:
            return
        audio_queue = self.hass.data[KEY_ASSIST_PIPELINE].device_audio_queues.get(
            self._device_id
        )
        if audio_queue is None:
            return
        try:
            audio_queue.queue.put_nowait(audio_bytes)
        except asyncio.QueueFull:
            audio_queue.overflow = True
            _LOGGER.warning("Audio queue full for device %s", self._device_id)

    @callback
    def start_debug_recording(self, name: str) -> None:
        """Start a new debug WAV file if recording is active."""
        if self.debug_recording_queue is not None:
            self.debug_recording_queue.put_nowait(name)

    def _start_debug_recording_thread(self) -> None:
        """Start the debug recording thread if configured."""
        assert self.debug_recording_thread is None
        if debug_recording_dir := self.hass.data[DATA_CONFIG].get(
            CONF_DEBUG_RECORDING_DIR
        ):
            if self._device_id is None:
                run_recording_dir = (
                    Path(debug_recording_dir)
                    / self.pipeline.name
                    / str(time.monotonic_ns())
                )
            else:
                run_recording_dir = (
                    Path(debug_recording_dir)
                    / self._device_id
                    / self.pipeline.name
                    / str(time.monotonic_ns())
                )
            self.debug_recording_queue = Queue()
            self.debug_recording_thread = Thread(
                target=_pipeline_debug_recording_thread_proc,
                args=(run_recording_dir, self.debug_recording_queue),
                daemon=True,
            )
            self.debug_recording_thread.start()

    async def _stop_debug_recording_thread(self) -> None:
        """Stop the debug recording thread."""
        if self.debug_recording_thread is None or self.debug_recording_queue is None:
            return
        await self.hass.async_add_executor_job(self.debug_recording_thread.join)
        self.debug_recording_queue = None
        self.debug_recording_thread = None


@dataclass(kw_only=True)
class PipelineInput:
    """Input to a pipeline run."""

    run: PipelineRun
    session: chat_session.ChatSession
    stt_metadata: stt.SpeechMetadata | None = None
    stt_stream: AsyncIterable[bytes] | None = None
    wake_word_phrase: str | None = None
    intent_input: str | None = None
    tts_input: str | None = None
    conversation_extra_system_prompt: str | None = None
    device_id: str | None = None
    satellite_id: str | None = None

    async def execute(self, validate: bool = False) -> None:
        """Run pipeline."""
        await self.run.async_execute(self, validate=validate)

    async def validate(self) -> None:
        """Validate pipeline input against start stage."""
        await self.run.async_validate(self)

    def create_processor_request(self) -> _PipelineProcessorRequest:
        """Create the private request passed to the pipeline processor."""
        return _PipelineProcessorRequest(
            session=self.session,
            stt_metadata=self.stt_metadata,
            stt_stream=self.stt_stream,
            wake_word_phrase=self.wake_word_phrase,
            intent_input=self.intent_input,
            tts_input=self.tts_input,
            conversation_extra_system_prompt=self.conversation_extra_system_prompt,
            device_id=self.device_id,
            satellite_id=self.satellite_id,
        )


def _create_pipeline_processor(run: PipelineRun) -> _PipelineProcessor:
    """Create the default pipeline processor."""
    return _DefaultPipelineProcessor(run)


def _pipeline_debug_recording_thread_proc(
    run_recording_dir: Path,
    queue: Queue[str | bytes | None],
    message_timeout: float = 5,
) -> None:
    """Write pipeline audio to debug WAV files."""
    wav_writer: wave.Wave_write | None = None
    try:
        _LOGGER.debug("Saving wake/stt audio to %s", run_recording_dir)
        run_recording_dir.mkdir(parents=True, exist_ok=True)
        while True:
            message = queue.get(timeout=message_timeout)
            if message is None:
                break
            if isinstance(message, str):
                if wav_writer is not None:
                    wav_writer.close()
                wav_path = run_recording_dir / f"{message}.wav"
                wav_writer = wave.open(str(wav_path), "wb")
                wav_writer.setframerate(SAMPLE_RATE)
                wav_writer.setsampwidth(SAMPLE_WIDTH)
                wav_writer.setnchannels(SAMPLE_CHANNELS)
            elif isinstance(message, bytes) and wav_writer is not None:
                wav_writer.writeframes(message)
    except Empty:
        pass
    except Exception:
        _LOGGER.exception("Unexpected error in debug recording thread")
    finally:
        if wav_writer is not None:
            wav_writer.close()
