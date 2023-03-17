"""Classes for voice assistant pipelines."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.backports.enum import StrEnum
from homeassistant.components import conversation, tts
from homeassistant.core import Context, HomeAssistant
from homeassistant.util.dt import utcnow

DEFAULT_TIMEOUT = 30  # seconds


@dataclass
class PipelineRequest:
    """Request to start a pipeline run."""

    intent_input: str
    conversation_id: str | None = None
    tts_input: str | None = None


class PipelineEventType(StrEnum):
    """Event types emitted during a pipeline run."""

    RUN_START = "run-start"
    RUN_FINISH = "run-finish"
    INTENT_START = "intent-start"
    INTENT_FINISH = "intent-finish"
    TTS_START = "tts-start"
    TTS_FINISH = "tts-finish"
    ERROR = "error"


class PipelineStage(StrEnum):
    """Stages in a pipeline."""

    INTENT = "intent"
    TTS = "tts"


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
    tts_engine: str

    async def run(
        self,
        hass: HomeAssistant,
        context: Context,
        request: PipelineRequest,
        event_callback: Callable[[PipelineEvent], None],
        start_stage: PipelineStage | None = None,
        stop_stage: PipelineStage | None = None,
        timeout: int | float | None = DEFAULT_TIMEOUT,
    ) -> None:
        """Run a pipeline with an optional timeout."""
        if start_stage is None:
            start_stage = PipelineStage.INTENT

        if stop_stage is None:
            stop_stage = PipelineStage.TTS

        await asyncio.wait_for(
            self._run(hass, context, request, event_callback, start_stage, stop_stage),
            timeout=timeout,
        )

    async def _run(
        self,
        hass: HomeAssistant,
        context: Context,
        request: PipelineRequest,
        event_callback: Callable[[PipelineEvent], None],
        start_stage: PipelineStage,
        stop_stage: PipelineStage,
    ) -> None:
        """Run a pipeline."""
        # Need to add intermediary stages when there are more than 2
        stages = {start_stage, stop_stage}

        language = self.language or hass.config.language
        event_callback(
            PipelineEvent(
                PipelineEventType.RUN_START,
                {
                    "pipeline": self.name,
                    "language": language,
                },
            )
        )

        intent_input = request.intent_input
        tts_input = request.tts_input

        if (PipelineStage.INTENT in stages) and (intent_input is not None):
            conversation_result = await self._recognize_intent(
                hass,
                context,
                language,
                intent_input,
                request.conversation_id,
                event_callback,
            )

            tts_input = conversation_result.response.speech.get("plain", {}).get(
                "speech", ""
            )

        if (PipelineStage.TTS in stages) and (tts_input is not None):
            await self._text_to_speech(hass, tts_input, event_callback)

        event_callback(
            PipelineEvent(
                PipelineEventType.RUN_FINISH,
            )
        )

    async def _recognize_intent(
        self,
        hass: HomeAssistant,
        context: Context,
        language: str,
        intent_input: str,
        conversation_id: str | None,
        event_callback: Callable[[PipelineEvent], None],
    ) -> conversation.ConversationResult:
        """Run intent recognition engine."""
        event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {
                    "engine": self.conversation_engine or "default",
                    "intent_input": intent_input,
                },
            )
        )

        conversation_result = await conversation.async_converse(
            hass=hass,
            text=intent_input,
            conversation_id=conversation_id,
            context=context,
            language=language,
            agent_id=self.conversation_engine,
        )

        event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_FINISH,
                {"intent_output": conversation_result.as_dict()},
            )
        )

        return conversation_result

    async def _text_to_speech(
        self,
        hass: HomeAssistant,
        tts_input: str,
        event_callback: Callable[[PipelineEvent], None],
    ) -> str:
        """Run text to speech engine."""
        event_callback(
            PipelineEvent(
                PipelineEventType.TTS_START,
                {
                    "engine": self.tts_engine,
                    "tts_input": tts_input,
                },
            )
        )

        manager: tts.SpeechManager = hass.data[tts.DOMAIN]
        tts_url = await manager.async_get_url_path(self.tts_engine, tts_input)

        event_callback(
            PipelineEvent(
                PipelineEventType.TTS_FINISH,
                {"tts_output": tts_url},
            )
        )

        return tts_url
