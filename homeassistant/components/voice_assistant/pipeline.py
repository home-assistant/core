"""Classes for voice assistant pipelines."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.backports.enum import StrEnum
from homeassistant.components import conversation, tts
from homeassistant.core import Context, HomeAssistant
from homeassistant.util.dt import utcnow

DEFAULT_TIMEOUT = 30  # seconds


class PipelineEventType(StrEnum):
    """Event types emitted during a pipeline run."""

    RUN_START = "run-start"
    RUN_FINISH = "run-finish"
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
    conversation_engine: str | None
    tts_engine: str | None


@dataclass
class PipelineRequest(ABC):
    """Request to for a pipeline run."""

    @abstractmethod
    async def execute(
        self,
        hass: HomeAssistant,
        context: Context,
        pipeline: Pipeline,
        event_callback: Callable[[PipelineEvent], None],
        timeout: int | float | None = DEFAULT_TIMEOUT,
    ):
        """Run pipeline with request info and context."""


@dataclass
class TextPipelineRequest(PipelineRequest):
    """Request to run the text portion only of a pipeline."""

    intent_input: str
    conversation_id: str | None = None

    async def execute(
        self,
        hass: HomeAssistant,
        context: Context,
        pipeline: Pipeline,
        event_callback: Callable[[PipelineEvent], None],
        timeout: int | float | None = DEFAULT_TIMEOUT,
    ):
        """Run text portion of pipeline."""
        await asyncio.wait_for(
            self._execute(hass, context, pipeline, event_callback),
            timeout=timeout,
        )

    async def _execute(
        self,
        hass: HomeAssistant,
        context: Context,
        pipeline: Pipeline,
        event_callback: Callable[[PipelineEvent], None],
    ):
        language = pipeline.language or hass.config.language
        event_callback(
            PipelineEvent(
                PipelineEventType.RUN_START,
                {
                    "pipeline": pipeline.name,
                    "language": language,
                },
            )
        )

        # Intent recognition
        intent_input = self.intent_input
        event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {
                    "engine": pipeline.conversation_engine or "default",
                    "intent_input": intent_input,
                },
            )
        )

        conversation_result = await conversation.async_converse(
            hass=hass,
            text=intent_input,
            conversation_id=self.conversation_id,
            context=context,
            language=language,
            agent_id=pipeline.conversation_engine,
        )

        event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_FINISH,
                {"intent_output": conversation_result.as_dict()},
            )
        )

        event_callback(
            PipelineEvent(
                PipelineEventType.RUN_FINISH,
            )
        )


@dataclass
class AudioPipelineRequest(PipelineRequest):
    """Request to full pipeline from audio input (stt) to audio output (tts)."""

    intent_input: str  # this will be changed to stt audio
    tts_input: str
    conversation_id: str | None = None

    async def execute(
        self,
        hass: HomeAssistant,
        context: Context,
        pipeline: Pipeline,
        event_callback: Callable[[PipelineEvent], None],
        timeout: int | float | None = DEFAULT_TIMEOUT,
    ):
        """Run full pipeline from audio input (stt) to audio output (tts)."""
        await asyncio.wait_for(
            self._execute(hass, context, pipeline, event_callback),
            timeout=timeout,
        )

    async def _execute(
        self,
        hass: HomeAssistant,
        context: Context,
        pipeline: Pipeline,
        event_callback: Callable[[PipelineEvent], None],
    ):
        language = pipeline.language or hass.config.language
        event_callback(
            PipelineEvent(
                PipelineEventType.RUN_START,
                {
                    "pipeline": pipeline.name,
                    "language": language,
                },
            )
        )

        # stt will go here

        # Intent recognition
        intent_input = self.intent_input
        event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {
                    "engine": pipeline.conversation_engine or "default",
                    "intent_input": intent_input,
                },
            )
        )

        conversation_result = await conversation.async_converse(
            hass=hass,
            text=intent_input,
            conversation_id=self.conversation_id,
            context=context,
            language=language,
            agent_id=pipeline.conversation_engine,
        )

        event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_FINISH,
                {"intent_output": conversation_result.as_dict()},
            )
        )

        # Text to speech
        event_callback(
            PipelineEvent(
                PipelineEventType.TTS_START,
                {
                    "engine": pipeline.tts_engine,
                    "tts_input": self.tts_input,
                },
            )
        )

        manager: tts.SpeechManager = hass.data[tts.DOMAIN]
        tts_url = await manager.async_get_url_path(pipeline.tts_engine, self.tts_input)

        event_callback(
            PipelineEvent(
                PipelineEventType.TTS_FINISH,
                {"tts_output": tts_url},
            )
        )

        event_callback(
            PipelineEvent(
                PipelineEventType.RUN_FINISH,
            )
        )
