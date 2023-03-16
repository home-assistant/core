"""Classes for voice assistant pipelines."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.util.dt import utcnow

DEFAULT_TIMEOUT = 30  # seconds


@dataclass
class PipelineRequest:
    """Request to start a pipeline run."""

    intent_input: str | None = None
    conversation_id: str | None = None


class PipelineEventType(str, Enum):
    """Event types emitted during a pipeline run."""

    RUN_START = "run-start"
    RUN_FINISH = "run-finish"
    INTENT_START = "intent-start"
    INTENT_FINISH = "intent-finish"
    ERROR = "error"


@dataclass
class PipelineEvent:
    """Events emitted during a pipeline run."""

    type: PipelineEventType
    data: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: utcnow().isoformat())

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the event."""
        return {"type": self.type, "timestamp": self.timestamp, "data": self.data or {}}


@dataclass
class Pipeline:
    """A voice assistant pipeline."""

    name: str
    language: str
    conversation_engine: str | None

    async def run(
        self,
        hass: HomeAssistant,
        context: Context,
        request: PipelineRequest,
        event_callback: Callable[[PipelineEvent], None],
        timeout: int | float | None = DEFAULT_TIMEOUT,
    ) -> None:
        """Run a pipeline with an optional timeout."""
        await asyncio.wait_for(
            self._run(hass, context, request, event_callback), timeout=timeout
        )

    async def _run(
        self,
        hass: HomeAssistant,
        context: Context,
        request: PipelineRequest,
        event_callback: Callable[[PipelineEvent], None],
    ) -> None:
        """Run a pipeline."""
        event_callback(
            PipelineEvent(
                PipelineEventType.RUN_START,
                {
                    "pipeline": self.name,
                    "language": self.language,
                },
            )
        )

        intent_input = request.intent_input or ""

        event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {"engine": self.conversation_engine or "default"},
            )
        )

        conversation_result = await conversation.async_converse(
            hass=hass,
            text=intent_input,
            conversation_id=request.conversation_id,
            context=context,
            language=self.language,
            agent_id=self.conversation_engine,
        )

        tts_input: str | None = conversation_result.response.speech.get(
            "plain", {}
        ).get("speech")
        event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_FINISH,
                {
                    "speech": tts_input,
                    "response": conversation_result.response.as_dict(),
                },
            )
        )

        event_callback(
            PipelineEvent(
                PipelineEventType.RUN_FINISH,
                {
                    "intent_input": intent_input,
                    "conversation_result": conversation_result,
                },
            )
        )
