"""Classes for voice assistant pipelines."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Callable
from dataclasses import asdict, dataclass, field
import logging
from typing import Any

from homeassistant.backports.enum import StrEnum
from homeassistant.components import conversation, media_source, stt
from homeassistant.components.tts.media_source import (
    generate_media_source_id as tts_generate_media_source_id,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.util.dt import utcnow

from .const import DOMAIN

DEFAULT_TIMEOUT = 30  # seconds

_LOGGER = logging.getLogger(__name__)


@callback
def async_get_pipeline(
    hass: HomeAssistant, pipeline_id: str | None = None, language: str | None = None
) -> Pipeline | None:
    """Get a pipeline by id or create one for a language."""
    if pipeline_id is not None:
        return hass.data[DOMAIN].get(pipeline_id)

    # Construct a pipeline for the required/configured language
    language = language or hass.config.language
    return Pipeline(
        name=language,
        language=language,
        stt_engine=None,  # first engine
        conversation_engine=None,  # first agent
        tts_engine=None,  # first engine
    )


class PipelineError(Exception):
    """Base class for pipeline errors."""

    def __init__(self, code: str, message: str) -> None:
        """Set error message."""
        self.code = code
        self.message = message

        super().__init__(f"Pipeline error code={code}, message={message}")


class SpeechToTextError(PipelineError):
    """Error in speech to text portion of pipeline."""


class IntentRecognitionError(PipelineError):
    """Error in intent recognition portion of pipeline."""


class TextToSpeechError(PipelineError):
    """Error in text to speech portion of pipeline."""


class PipelineEventType(StrEnum):
    """Event types emitted during a pipeline run."""

    RUN_START = "run-start"
    RUN_END = "run-end"
    STT_START = "stt-start"
    STT_END = "stt-end"
    INTENT_START = "intent-start"
    INTENT_END = "intent-end"
    TTS_START = "tts-start"
    TTS_END = "tts-end"
    ERROR = "error"


@dataclass
class PipelineEvent:
    """Events emitted during a pipeline run."""

    type: PipelineEventType
    data: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: utcnow().isoformat())

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the event."""
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "data": self.data or {},
        }


@dataclass
class Pipeline:
    """A voice assistant pipeline."""

    name: str
    language: str | None
    stt_engine: str | None
    conversation_engine: str | None
    tts_engine: str | None


class PipelineStage(StrEnum):
    """Stages of a pipeline."""

    STT = "stt"
    INTENT = "intent"
    TTS = "tts"


PIPELINE_STAGE_ORDER = [
    PipelineStage.STT,
    PipelineStage.INTENT,
    PipelineStage.TTS,
]


class PipelineRunValidationError(Exception):
    """Error when a pipeline run is not valid."""


class InvalidPipelineStagesError(PipelineRunValidationError):
    """Error when given an invalid combination of start/end stages."""

    def __init__(
        self,
        start_stage: PipelineStage,
        end_stage: PipelineStage,
    ) -> None:
        """Set error message."""
        super().__init__(
            f"Invalid stage combination: start={start_stage}, end={end_stage}"
        )


@dataclass
class PipelineRun:
    """Running context for a pipeline."""

    hass: HomeAssistant
    context: Context
    pipeline: Pipeline
    start_stage: PipelineStage
    end_stage: PipelineStage
    event_callback: Callable[[PipelineEvent], None]
    language: str = None  # type: ignore[assignment]
    runner_data: Any | None = None

    def __post_init__(self):
        """Set language for pipeline."""
        self.language = self.pipeline.language or self.hass.config.language

        # stt -> intent -> tts
        if PIPELINE_STAGE_ORDER.index(self.end_stage) < PIPELINE_STAGE_ORDER.index(
            self.start_stage
        ):
            raise InvalidPipelineStagesError(self.start_stage, self.end_stage)

    def start(self):
        """Emit run start event."""
        data = {
            "pipeline": self.pipeline.name,
            "language": self.language,
        }
        if self.runner_data is not None:
            data["runner_data"] = self.runner_data

        self.event_callback(PipelineEvent(PipelineEventType.RUN_START, data))

    def end(self):
        """Emit run end event."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.RUN_END,
            )
        )

    async def speech_to_text(
        self,
        metadata: stt.SpeechMetadata,
        stream: AsyncIterable[bytes],
    ) -> str:
        """Run speech to text portion of pipeline. Returns the spoken text."""
        engine = self.pipeline.stt_engine or "default"
        self.event_callback(
            PipelineEvent(
                PipelineEventType.STT_START,
                {
                    "engine": engine,
                    "metadata": asdict(metadata),
                },
            )
        )

        try:
            # Load provider
            stt_provider: stt.Provider = stt.async_get_provider(
                self.hass, self.pipeline.stt_engine
            )
            assert stt_provider is not None
        except Exception as src_error:
            _LOGGER.exception("No speech to text provider for %s", engine)
            raise SpeechToTextError(
                code="stt-provider-missing",
                message=f"No speech to text provider for: {engine}",
            ) from src_error

        if not stt_provider.check_metadata(metadata):
            raise SpeechToTextError(
                code="stt-provider-unsupported-metadata",
                message=f"Provider {engine} does not support input speech to text metadata",
            )

        try:
            # Transcribe audio stream
            result = await stt_provider.async_process_audio_stream(metadata, stream)
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during speech to text")
            raise SpeechToTextError(
                code="stt-stream-failed",
                message="Unexpected error during speech to text",
            ) from src_error

        _LOGGER.debug("speech-to-text result %s", result)

        if result.result != stt.SpeechResultState.SUCCESS:
            raise SpeechToTextError(
                code="stt-stream-failed",
                message="Speech to text failed",
            )

        if not result.text:
            raise SpeechToTextError(
                code="stt-no-text-recognized", message="No text recognized"
            )

        self.event_callback(
            PipelineEvent(
                PipelineEventType.STT_END,
                {
                    "stt_output": {
                        "text": result.text,
                    }
                },
            )
        )

        return result.text

    async def recognize_intent(
        self, intent_input: str, conversation_id: str | None
    ) -> str:
        """Run intent recognition portion of pipeline. Returns text to speak."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {
                    "engine": self.pipeline.conversation_engine or "default",
                    "intent_input": intent_input,
                },
            )
        )

        try:
            conversation_result = await conversation.async_converse(
                hass=self.hass,
                text=intent_input,
                conversation_id=conversation_id,
                context=self.context,
                language=self.language,
                agent_id=self.pipeline.conversation_engine,
            )
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during intent recognition")
            raise IntentRecognitionError(
                code="intent-failed",
                message="Unexpected error during intent recognition",
            ) from src_error

        _LOGGER.debug("conversation result %s", conversation_result)

        self.event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_END,
                {"intent_output": conversation_result.as_dict()},
            )
        )

        speech = conversation_result.response.speech.get("plain", {}).get("speech", "")

        return speech

    async def text_to_speech(self, tts_input: str) -> str:
        """Run text to speech portion of pipeline. Returns URL of TTS audio."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.TTS_START,
                {
                    "engine": self.pipeline.tts_engine or "default",
                    "tts_input": tts_input,
                },
            )
        )

        try:
            # Synthesize audio and get URL
            tts_media = await media_source.async_resolve_media(
                self.hass,
                tts_generate_media_source_id(
                    self.hass,
                    tts_input,
                    engine=self.pipeline.tts_engine,
                ),
            )
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during text to speech")
            raise TextToSpeechError(
                code="tts-failed",
                message="Unexpected error during text to speech",
            ) from src_error

        _LOGGER.debug("TTS result %s", tts_media)

        self.event_callback(
            PipelineEvent(
                PipelineEventType.TTS_END,
                {"tts_output": asdict(tts_media)},
            )
        )

        return tts_media.url


@dataclass
class PipelineInput:
    """Input to a pipeline run."""

    stt_metadata: stt.SpeechMetadata | None = None
    """Metadata of stt input audio. Required when start_stage = stt."""

    stt_stream: AsyncIterable[bytes] | None = None
    """Input audio for stt. Required when start_stage = stt."""

    intent_input: str | None = None
    """Input for conversation agent. Required when start_stage = intent."""

    tts_input: str | None = None
    """Input for text to speech. Required when start_stage = tts."""

    conversation_id: str | None = None

    async def execute(
        self, run: PipelineRun, timeout: int | float | None = DEFAULT_TIMEOUT
    ):
        """Run pipeline with optional timeout."""
        await asyncio.wait_for(
            self._execute(run),
            timeout=timeout,
        )

    async def _execute(self, run: PipelineRun):
        self._validate(run.start_stage)

        # stt -> intent -> tts
        run.start()
        current_stage = run.start_stage

        try:
            # Speech to text
            intent_input = self.intent_input
            if current_stage == PipelineStage.STT:
                assert self.stt_metadata is not None
                assert self.stt_stream is not None
                intent_input = await run.speech_to_text(
                    self.stt_metadata,
                    self.stt_stream,
                )
                current_stage = PipelineStage.INTENT

            if run.end_stage != PipelineStage.STT:
                tts_input = self.tts_input

                if current_stage == PipelineStage.INTENT:
                    assert intent_input is not None
                    tts_input = await run.recognize_intent(
                        intent_input, self.conversation_id
                    )
                    current_stage = PipelineStage.TTS

                if run.end_stage != PipelineStage.INTENT:
                    if current_stage == PipelineStage.TTS:
                        assert tts_input is not None
                        await run.text_to_speech(tts_input)

        except PipelineError as err:
            run.event_callback(
                PipelineEvent(
                    PipelineEventType.ERROR,
                    {"code": err.code, "message": err.message},
                )
            )
            return

        run.end()

    def _validate(self, stage: PipelineStage):
        """Validate pipeline input against start stage."""
        if stage == PipelineStage.STT:
            if self.stt_metadata is None:
                raise PipelineRunValidationError(
                    "stt_metadata is required for speech to text"
                )

            if self.stt_stream is None:
                raise PipelineRunValidationError(
                    "stt_stream is required for speech to text"
                )
        elif stage == PipelineStage.INTENT:
            if self.intent_input is None:
                raise PipelineRunValidationError(
                    "intent_input is required for intent recognition"
                )
        elif stage == PipelineStage.TTS:
            if self.tts_input is None:
                raise PipelineRunValidationError(
                    "tts_input is required for text to speech"
                )
