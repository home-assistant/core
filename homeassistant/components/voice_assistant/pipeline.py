"""Classes for voice assistant pipelines."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass, field
from typing import Any


from homeassistant.backports.enum import StrEnum
from homeassistant.components import conversation, stt
from homeassistant.components.media_source import async_resolve_media
from homeassistant.components.tts.media_source import (
    generate_media_source_id as tts_generate_media_source_id,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.util.dt import utcnow

DEFAULT_TIMEOUT = 30  # seconds

_LOGGER = logging.getLogger(__name__)


class PipelineEventType(StrEnum):
    """Event types emitted during a pipeline run."""

    RUN_START = "run-start"
    RUN_FINISH = "run-finish"
    STT_START = "stt-start"
    STT_FINISH = "stt-finish"
    INTENT_START = "intent-start"
    INTENT_FINISH = "intent-finish"
    TTS_START = "tts-start"
    TTS_FINISH = "tts-finish"
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


@dataclass
class PipelineRun:
    """Running context for a pipeline."""

    hass: HomeAssistant
    context: Context
    pipeline: Pipeline
    event_callback: Callable[[PipelineEvent], None]
    language: str = None  # type: ignore[assignment]

    def __post_init__(self):
        """Set language for pipeline."""
        self.language = self.pipeline.language or self.hass.config.language

    def start(self):
        """Emit run start event."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.RUN_START,
                {
                    "pipeline": self.pipeline.name,
                    "language": self.language,
                },
            )
        )

    def finish(self):
        """Emit run finish event."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.RUN_FINISH,
            )
        )

    async def speech_to_text(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Run text to speech portion of pipeline. Returns URL of TTS audio."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.STT_START,
                {
                    "engine": self.pipeline.stt_engine,
                },
            )
        )

        stt_provider = stt.async_get_provider(self.hass, self.pipeline.stt_engine)
        result = await stt_provider.async_process_audio_stream(metadata, stream)
        _LOGGER.debug("stt result: %s", result)

        self.event_callback(
            PipelineEvent(
                PipelineEventType.STT_FINISH,
                {
                    "stt_output": {
                        "text": result.text,
                        "result": result.result.value,
                    }
                },
            )
        )

        return result

    async def recognize_intent(
        self, intent_input: str, conversation_id: str | None
    ) -> conversation.ConversationResult:
        """Run intent recognition portion of pipeline."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {
                    "engine": self.pipeline.conversation_engine or "default",
                    "intent_input": intent_input,
                },
            )
        )

        conversation_result = await conversation.async_converse(
            hass=self.hass,
            text=intent_input,
            conversation_id=conversation_id,
            context=self.context,
            language=self.language,
            agent_id=self.pipeline.conversation_engine,
        )
        _LOGGER.debug("intent result: %s", conversation_result)

        self.event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_FINISH,
                {"intent_output": conversation_result.as_dict()},
            )
        )

        return conversation_result

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

        tts_media = await async_resolve_media(
            self.hass,
            tts_generate_media_source_id(
                self.hass,
                tts_input,
                engine=self.pipeline.tts_engine,
            ),
        )
        _LOGGER.debug("tts result: %s", tts_media)

        self.event_callback(
            PipelineEvent(
                PipelineEventType.TTS_FINISH,
                {"tts_output": tts_media.url},
            )
        )

        return tts_media.url


@dataclass
class PipelineRequest(ABC):
    """Request to for a pipeline run."""

    async def execute(
        self, run: PipelineRun, timeout: int | float | None = DEFAULT_TIMEOUT
    ):
        """Run pipeline with optional timeout."""
        await asyncio.wait_for(
            self._execute(run),
            timeout=timeout,
        )

    @abstractmethod
    async def _execute(self, run: PipelineRun):
        """Run pipeline with request info and context."""


@dataclass
class TextPipelineRequest(PipelineRequest):
    """Request to run the text portion only of a pipeline."""

    intent_input: str
    conversation_id: str | None = None

    async def _execute(
        self,
        run: PipelineRun,
    ):
        run.start()
        await run.recognize_intent(self.intent_input, self.conversation_id)
        run.finish()


@dataclass
class AudioPipelineRequest(PipelineRequest):
    """Request to full pipeline from audio input (stt) to audio output (tts)."""

    stt_metadata: stt.SpeechMetadata
    stt_stream: AsyncIterable[bytes]
    conversation_id: str | None = None

    async def _execute(self, run: PipelineRun):
        run.start()

        stt_result = await run.speech_to_text(self.stt_metadata, self.stt_stream)
        if stt_result.result == stt.SpeechResultState.SUCCESS:
            assert stt_result.text is not None

            conversation_result = await run.recognize_intent(
                stt_result.text, self.conversation_id
            )

            tts_input = conversation_result.response.speech.get("plain", {}).get(
                "speech", ""
            )

            await run.text_to_speech(tts_input)

        run.finish()
