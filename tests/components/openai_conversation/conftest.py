"""Tests helpers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from openai.types import ResponseFormatText
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

from homeassistant.components.openai_conversation.const import (
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.conversation import mock_chat_log  # noqa: F401


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        title="OpenAI",
        domain="openai_conversation",
        data={
            "api_key": "bla",
        },
        version=2,
        subentries_data=[
            {
                "data": {},
                "subentry_type": "conversation",
                "title": DEFAULT_CONVERSATION_NAME,
                "unique_id": None,
            },
            {
                "data": {},
                "subentry_type": "ai_task",
                "title": DEFAULT_AI_TASK_NAME,
                "unique_id": None,
            },
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_config_entry_with_assist(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Mock a config entry with assist."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={CONF_LLM_HASS_API: llm.LLM_API_ASSIST},
    )
    return mock_config_entry


@pytest.fixture
async def mock_init_component(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Initialize integration."""
    with patch(
        "openai.resources.models.AsyncModels.list",
    ):
        assert await async_setup_component(hass, "openai_conversation", {})
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def mock_create_stream() -> Generator[AsyncMock]:
    """Mock stream response."""

    async def mock_generator(events, **kwargs):
        response = Response(
            id="resp_A",
            created_at=1700000000,
            error=None,
            incomplete_details=None,
            instructions=kwargs.get("instructions"),
            metadata=kwargs.get("metadata", {}),
            model=kwargs.get("model", "gpt-4o-mini"),
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
            user=kwargs.get("user"),
            store=kwargs.get("store", True),
        )
        yield ResponseCreatedEvent(
            response=response,
            type="response.created",
        )
        yield ResponseInProgressEvent(
            response=response,
            type="response.in_progress",
        )
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

            yield value

            if isinstance(value, ResponseErrorEvent):
                return

        if response.status == "incomplete":
            yield ResponseIncompleteEvent(
                response=response,
                type="response.incomplete",
            )
        elif response.status == "failed":
            yield ResponseFailedEvent(
                response=response,
                type="response.failed",
            )
        else:
            yield ResponseCompletedEvent(
                response=response,
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
