"""Classes for voice assistant pipelines."""
from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any

from aiohttp import StreamReader

from homeassistant.components import conversation, stt
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
    timestamp: int = field(default_factory=time.monotonic_ns)

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the event."""
        return {"type": self.type, "timestamp": self.timestamp, "data": self.data or {}}


@dataclass
class Pipeline:
    """A voice assistant pipeline."""

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
    ) -> AsyncIterable[PipelineEvent]:
        """Run a pipeline."""
        yield PipelineEvent(PipelineEventType.RUN_START, {})

        # TODO validate that pipeline contains valid engines for STT/TTS

        stt_text = request.stt_text
        # if stt_text is None:
        #     # Run speech to text
        #     if (request.stt_audio is None) or (request.stt_metadata is None):
        #         yield PipelineEvent(
        #             PipelineEventType.ERROR,
        #             {
        #                 "code": "bad_input",
        #                 "message": "STT audio and metadata is required if text is missing",
        #             },
        #         )

        #     stt_provider = stt.async_get_provider(hass, self.stt_engine)
        #     yield PipelineEvent(
        #         PipelineEventType.STT_START, {"engine": self.stt_engine}
        #     )
        #     stt_result = await stt_provider.async_process_audio_stream(
        #         request.stt_metadata, request.stt_audio
        #     )
        #     stt_text = stt_result.text
        #     yield PipelineEvent(PipelineEventType.STT_FINISH, {"text": stt_text})

        # Run intent recognition
        if stt_text is None:
            yield PipelineEvent(
                PipelineEventType.ERROR,
                {
                    "code": "speech_not_recognized",
                    "message": "no speech returned from agent",
                },
            )
            return

        agent = await conversation.get_agent_manager(hass).async_get_agent(
            self.agent_id
        )
        yield PipelineEvent(
            PipelineEventType.INTENT_START,
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
            PipelineEventType.INTENT_FINISH,
            {"speech": tts_text, "response": conversation_result.response.as_dict()},
        )

        # Run text to speech
        if tts_text is None:
            yield PipelineEvent(
                PipelineEventType.ERROR,
                {
                    "code": "response_has_no_speech",
                    "message": "no speech returned from agent",
                },
            )
            return

        tts_url = None

        # Only output STT if we also did TTS
        # if request.stt_audio is not None:
        #     speech_manager: tts.SpeechManager = hass.data[tts.DOMAIN]
        #     yield PipelineEvent(
        #         PipelineEventType.TTS_START,
        #         {"engine": self.tts_engine},
        #     )
        #     tts_url = await speech_manager.async_get_url_path(self.tts_engine, tts_text)
        #     yield PipelineEvent(
        #         PipelineEventType.TTS_FINISH,
        #         {"url": tts_url},
        #     )

        yield PipelineEvent(
            PipelineEventType.RUN_FINISH,
            {
                "stt_text": stt_text,
                "conversation_result": conversation_result,
                "tts_url": tts_url,
            },
        )
