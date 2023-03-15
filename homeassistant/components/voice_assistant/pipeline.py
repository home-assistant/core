"""Classes for voice assistant pipelines."""
from __future__ import annotations

import time
from enum import Enum
from collections.abc import AsyncIterable
from dataclasses import dataclass, field
from typing import Any

from aiohttp import StreamReader

from homeassistant.components import conversation, stt, tts
from homeassistant.core import Context, HomeAssistant


@dataclass
class PipelineRequest:
    """Request to start a pipeline run."""

    stt_audio: StreamReader | None
    stt_metadata: stt.SpeechMetadata | None
    stt_text: str | None = None
    conversation_id: str | None = None


class PipelineEventType(str, Enum):
    """Event types emitted during a pipeline run."""

    STT_STARTED = "stt-started"
    STT_STOPPED = "stt-stopped"
    INTENT_STARTED = "intent-started"
    INTENT_STOPPED = "intent-stopped"
    TTS_STARTED = "tts-started"
    TTS_STOPPED = "tts-stopped"


@dataclass
class PipelineEvent:
    """Events emitted during a pipeline run."""

    type: PipelineEventType
    data: dict[str, Any] | None = None
    timestamp: int = field(default_factory=time.monotonic_ns)

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.type, "timestamp": self.timestamp, "data": self.data or {}}


@dataclass
class PipelineResponse:
    """Final response from a pipeline run."""

    stt_text: str
    conversation_result: conversation.ConversationResult
    tts_url: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "stt_text": self.stt_text,
            "conversation_result": self.conversation_result.as_dict(),
            "tts_url": self.tts_url,
        }


class PipelineError(Exception):
    """Base class for pipeline errors"""


class PipelineNoTranscriptError(PipelineError):
    """Error raised when STT doesn't return a transcript."""


class PipelineNoSpeechError(PipelineError):
    """Error raised when intent recogniton doesn't return any speech."""


@dataclass
class Pipeline:
    name: str
    language: str
    stt_engine: str
    agent_id: str
    tts_engine: str

    # output format for tts (bytes or media src url) - can be dynamic
    # get supported codecs for tts
    # raise error in get_provider
    # pcm output for azure?
    # pass in voice instead of gender
    #
    # pipeline platform?
    # output stream of events
    #
    # binary handler for websocket?
    #
    # NOTE: Use collection helper for storage
    # collection.async_add_change_set_listener(_collection_changed)
    # collection.StorageCollectionWebsocket(
    #     storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    # ).async_setup(hass)
    #
    # TODO: Add intent parse/executed events to conversation

    async def run(
        self, hass: HomeAssistant, context: Context, request: PipelineRequest
    ) -> AsyncIterable[PipelineEvent | PipelineResponse]:
        """Runs a pipeline, emitting events and a final response."""
        stt_text = request.stt_text
        if stt_text is None:
            # Run speech to text
            if (request.stt_audio is None) or (request.stt_metadata is None):
                raise PipelineError(
                    f"Pipeline {self.name}: STT audio and metadata is required if text is missing"
                )

            stt_provider = stt.async_get_provider(hass, self.stt_engine)
            yield PipelineEvent(
                PipelineEventType.STT_STARTED, {"engine": self.stt_engine}
            )
            stt_result = await stt_provider.async_process_audio_stream(
                request.stt_metadata, request.stt_audio
            )
            stt_text = stt_result.text
            yield PipelineEvent(PipelineEventType.STT_STOPPED, {"text": stt_text})

        # Run intent recognition
        if stt_text is None:
            raise PipelineNoTranscriptError(
                f"Pipeline {self.name}: no transcript returned from STT"
            )

        agent = await conversation.get_agent_manager(hass).async_get_agent(
            self.agent_id
        )
        yield PipelineEvent(
            PipelineEventType.INTENT_STARTED,
            {"agent_id": self.agent_id},
        )
        conversation_result = await agent.async_process(
            conversation.ConversationInput(
                text=stt_text,
                context=context,
                conversation_id=request.conversation_id,
                language=self.language,
            )
        )

        tts_text: str | None = conversation_result.response.speech.get("plain", {}).get(
            "speech"
        )
        yield PipelineEvent(
            PipelineEventType.INTENT_STOPPED,
            {"speech": tts_text, "response": conversation_result.response.as_dict()},
        )

        # Run text to speech
        if tts_text is None:
            raise PipelineNoSpeechError(
                f"Pipeline {self.name}: no speech returned from agent"
            )

        speech_manager: tts.SpeechManager = hass.data[tts.DOMAIN]
        yield PipelineEvent(
            PipelineEventType.TTS_STARTED,
            {"engine": self.tts_engine},
        )
        tts_url = await speech_manager.async_get_url_path(self.tts_engine, tts_text)
        yield PipelineEvent(
            PipelineEventType.TTS_STOPPED,
            {"url": tts_url},
        )

        yield PipelineResponse(stt_text, conversation_result, tts_url)
