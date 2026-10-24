"""Tests helpers."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from openai.types import ResponseFormatText
from openai.types.audio import Transcription
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseError,
    ResponseErrorEvent,
    ResponseFailedEvent,
    ResponseIncompleteEvent,
    ResponseInProgressEvent,
    ResponseOutputItemDoneEvent,
    ResponseTextConfig,
)
from openai.types.responses.response import IncompleteDetails
import pytest

from homeassistant.components.azure_openai.const import (
    CONF_CHAT_MODEL,
    CONF_MODEL_FAMILY,
    CONF_STT_MODEL,
    CONF_TTS_MODEL,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_TTS_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TTS_OPTIONS,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.conversation import mock_chat_log  # noqa: F401

# Deployment names are deliberately unrelated to their model family strings so
# tests can prove request routing and capability gating are driven by the two
# independently, never by parsing the deployment name.
MOCK_CHAT_DEPLOYMENT = "chat-deployment"
MOCK_CHAT_MODEL_FAMILY = "gpt-4o-mini"
MOCK_STT_DEPLOYMENT = "stt-deployment"
MOCK_STT_MODEL = "gpt-4o-transcribe"
MOCK_TTS_DEPLOYMENT = "tts-deployment"
MOCK_TTS_MODEL = "gpt-4o-mini-tts"


@pytest.fixture
def mock_conversation_subentry_data() -> dict[str, Any]:
    """Mock subentry data."""
    return {
        CONF_CHAT_MODEL: MOCK_CHAT_DEPLOYMENT,
        CONF_MODEL_FAMILY: MOCK_CHAT_MODEL_FAMILY,
    }


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_conversation_subentry_data: dict[str, Any]
) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        title="Azure OpenAI",
        domain=DOMAIN,
        data={
            "api_key": "bla",
            "base_url": "https://example.openai.azure.com/openai/v1/",
        },
        version=1,
        subentries_data=[
            ConfigSubentryData(
                data=mock_conversation_subentry_data,
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    **RECOMMENDED_AI_TASK_OPTIONS,
                    CONF_CHAT_MODEL: MOCK_CHAT_DEPLOYMENT,
                    CONF_MODEL_FAMILY: MOCK_CHAT_MODEL_FAMILY,
                },
                subentry_type="ai_task_data",
                title=DEFAULT_AI_TASK_NAME,
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    **RECOMMENDED_STT_OPTIONS,
                    CONF_CHAT_MODEL: MOCK_STT_DEPLOYMENT,
                    CONF_STT_MODEL: MOCK_STT_MODEL,
                },
                subentry_type="stt",
                title=DEFAULT_STT_NAME,
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    **RECOMMENDED_TTS_OPTIONS,
                    CONF_CHAT_MODEL: MOCK_TTS_DEPLOYMENT,
                    CONF_TTS_MODEL: MOCK_TTS_MODEL,
                },
                subentry_type="tts",
                title=DEFAULT_TTS_NAME,
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_config_entry_with_assist(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Mock a config entry with assist."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
            CONF_CHAT_MODEL: MOCK_CHAT_DEPLOYMENT,
            CONF_MODEL_FAMILY: MOCK_CHAT_MODEL_FAMILY,
        },
    )
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
async def mock_config_entry_with_reasoning_model(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Mock a config entry with assist, backed by a reasoning-capable family."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
            CONF_CHAT_MODEL: MOCK_CHAT_DEPLOYMENT,
            CONF_MODEL_FAMILY: "gpt-5-mini",
        },
    )
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
async def mock_init_component(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> AsyncGenerator[None]:
    """Initialize integration."""
    with patch(
        "openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def mock_create_stream() -> Generator[AsyncMock]:
    """Mock stream response."""

    async def mock_generator(events, **kwargs):
        if isinstance(events, Exception):
            raise events
        response = Response(
            id="resp_A",
            created_at=1700000000,
            error=None,
            incomplete_details=None,
            instructions=kwargs.get("instructions"),
            metadata=kwargs.get("metadata", {}),
            model=kwargs.get("model", MOCK_CHAT_DEPLOYMENT),
            object="response",
            output=[],
            parallel_tool_calls=kwargs.get("parallel_tool_calls", True),
            temperature=kwargs.get("temperature", 1.0),
            tool_choice=kwargs.get("tool_choice", "auto"),
            tools=kwargs.get("tools", []),
            top_p=kwargs.get("top_p", 1.0),
            max_output_tokens=kwargs.get("max_output_tokens", 100000),
            previous_response_id=kwargs.get("previous_response_id"),
            reasoning=kwargs.get("reasoning"),
            status="in_progress",
            text=kwargs.get(
                "text", ResponseTextConfig(format=ResponseFormatText(type="text"))
            ),
            truncation=kwargs.get("truncation", "disabled"),
            usage=None,
            safety_identifier=kwargs.get("safety_identifier"),
            store=kwargs.get("store", True),
        )
        yield ResponseCreatedEvent(
            response=response,
            sequence_number=0,
            type="response.created",
        )
        yield ResponseInProgressEvent(
            response=response,
            sequence_number=1,
            type="response.in_progress",
        )
        sequence_number = 2
        response.status = "completed"

        for value in events:
            if isinstance(value, ResponseOutputItemDoneEvent):
                response.output.append(value.item)
            elif isinstance(value, IncompleteDetails):
                response.status = "incomplete"
                response.incomplete_details = value
                break
            if isinstance(value, ResponseError):
                response.status = "failed"
                response.error = value
                break

            value.sequence_number = sequence_number
            sequence_number += 1
            yield value

            if isinstance(value, ResponseErrorEvent):
                return

        if response.status == "incomplete":
            yield ResponseIncompleteEvent(
                response=response,
                sequence_number=sequence_number,
                type="response.incomplete",
            )
        elif response.status == "failed":
            yield ResponseFailedEvent(
                response=response,
                sequence_number=sequence_number,
                type="response.failed",
            )
        else:
            yield ResponseCompletedEvent(
                response=response,
                sequence_number=sequence_number,
                type="response.completed",
            )

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        AsyncMock(),
    ) as mock_create:
        mock_create.side_effect = lambda **kwargs: mock_generator(
            mock_create.return_value.pop(0), **kwargs
        )

        yield mock_create


@pytest.fixture
def mock_create_transcription() -> Generator[AsyncMock]:
    """Mock transcription response."""

    with patch(
        "openai.resources.audio.transcriptions.AsyncTranscriptions.create",
        AsyncMock(return_value=""),
    ) as mock_create:
        mock_create.side_effect = lambda *args, **kwargs: (
            Transcription(text=mock_create.return_value)
            if isinstance(mock_create.return_value, str)
            else mock_create.return_value
        )
        yield mock_create


@pytest.fixture
def mock_create_speech() -> Generator[MagicMock]:
    """Mock stream response."""

    class AsyncIterBytesHelper:
        def __init__(self, chunks) -> None:
            self.chunks = chunks
            self.index = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.index]
            self.index += 1
            return chunk

    mock_response = MagicMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_response
    mock_create = MagicMock(side_effect=lambda **kwargs: mock_cm)
    with patch(
        "openai.resources.audio.speech.async_to_custom_streamed_response_wrapper",
        return_value=mock_create,
    ):
        mock_response.iter_bytes.side_effect = lambda **kwargs: AsyncIterBytesHelper(
            mock_create.return_value
        )
        yield mock_create
