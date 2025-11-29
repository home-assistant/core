"""Tests helpers."""

from collections.abc import AsyncGenerator, Generator, Iterable
import datetime
from unittest.mock import AsyncMock, patch

from anthropic.pagination import AsyncPage
from anthropic.types import (
    Message,
    MessageDeltaUsage,
    ModelInfo,
    RawContentBlockStartEvent,
    RawMessageDeltaEvent,
    RawMessageStartEvent,
    RawMessageStopEvent,
    RawMessageStreamEvent,
    ToolUseBlock,
    Usage,
)
from anthropic.types.raw_message_delta_event import Delta
import pytest

from homeassistant.components.anthropic.const import (
    CONF_CHAT_MODEL,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_MAX_USES,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        title="Claude",
        domain="anthropic",
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
                "subentry_type": "ai_task_data",
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
def mock_config_entry_with_extended_thinking(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Mock a config entry with extended thinking."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
            CONF_CHAT_MODEL: "claude-3-7-sonnet-latest",
        },
    )
    return mock_config_entry


@pytest.fixture
def mock_config_entry_with_web_search(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Mock a config entry with server tools enabled."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
            CONF_CHAT_MODEL: "claude-sonnet-4-5",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_MAX_USES: 5,
            CONF_WEB_SEARCH_USER_LOCATION: True,
            CONF_WEB_SEARCH_CITY: "San Francisco",
            CONF_WEB_SEARCH_REGION: "California",
            CONF_WEB_SEARCH_COUNTRY: "US",
            CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
        },
    )
    return mock_config_entry


@pytest.fixture
async def mock_init_component(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> AsyncGenerator[None]:
    """Initialize integration."""
    model_list = AsyncPage(
        data=[
            ModelInfo(
                id="claude-haiku-4-5-20251001",
                created_at=datetime.datetime(2025, 10, 15, 0, 0, tzinfo=datetime.UTC),
                display_name="Claude Haiku 4.5",
                type="model",
            ),
            ModelInfo(
                id="claude-sonnet-4-5-20250929",
                created_at=datetime.datetime(2025, 9, 29, 0, 0, tzinfo=datetime.UTC),
                display_name="Claude Sonnet 4.5",
                type="model",
            ),
            ModelInfo(
                id="claude-opus-4-1-20250805",
                created_at=datetime.datetime(2025, 8, 5, 0, 0, tzinfo=datetime.UTC),
                display_name="Claude Opus 4.1",
                type="model",
            ),
            ModelInfo(
                id="claude-opus-4-20250514",
                created_at=datetime.datetime(2025, 5, 22, 0, 0, tzinfo=datetime.UTC),
                display_name="Claude Opus 4",
                type="model",
            ),
            ModelInfo(
                id="claude-sonnet-4-20250514",
                created_at=datetime.datetime(2025, 5, 22, 0, 0, tzinfo=datetime.UTC),
                display_name="Claude Sonnet 4",
                type="model",
            ),
            ModelInfo(
                id="claude-3-7-sonnet-20250219",
                created_at=datetime.datetime(2025, 2, 24, 0, 0, tzinfo=datetime.UTC),
                display_name="Claude Sonnet 3.7",
                type="model",
            ),
            ModelInfo(
                id="claude-3-5-haiku-20241022",
                created_at=datetime.datetime(2024, 10, 22, 0, 0, tzinfo=datetime.UTC),
                display_name="Claude Haiku 3.5",
                type="model",
            ),
            ModelInfo(
                id="claude-3-haiku-20240307",
                created_at=datetime.datetime(2024, 3, 7, 0, 0, tzinfo=datetime.UTC),
                display_name="Claude Haiku 3",
                type="model",
            ),
            ModelInfo(
                id="claude-3-opus-20240229",
                created_at=datetime.datetime(2024, 2, 29, 0, 0, tzinfo=datetime.UTC),
                display_name="Claude Opus 3",
                type="model",
            ),
        ]
    )
    with patch(
        "anthropic.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
        return_value=model_list,
    ):
        assert await async_setup_component(hass, "anthropic", {})
        await hass.async_block_till_done()
        yield


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def mock_create_stream() -> Generator[AsyncMock]:
    """Mock stream response."""

    async def mock_generator(events: Iterable[RawMessageStreamEvent], **kwargs):
        """Create a stream of messages with the specified content blocks."""
        stop_reason = "end_turn"
        refusal_magic_string = "ANTHROPIC_MAGIC_STRING_TRIGGER_REFUSAL_1FAEFB6177B4672DEE07F9D3AFC62588CCD2631EDCF22E8CCC1FB35B501C9C86"
        for message in kwargs.get("messages"):
            if message["role"] != "user":
                continue
            if isinstance(message["content"], str):
                if refusal_magic_string in message["content"]:
                    stop_reason = "refusal"
                    break
            else:
                for content in message["content"]:
                    if content.get(
                        "type"
                    ) == "text" and refusal_magic_string in content.get("text", ""):
                        stop_reason = "refusal"
                        break

        yield RawMessageStartEvent(
            message=Message(
                type="message",
                id="msg_1234567890ABCDEFGHIJKLMN",
                content=[],
                role="assistant",
                model="claude-3-5-sonnet-20240620",
                usage=Usage(input_tokens=0, output_tokens=0),
            ),
            type="message_start",
        )
        for event in events:
            if isinstance(event, RawContentBlockStartEvent) and isinstance(
                event.content_block, ToolUseBlock
            ):
                stop_reason = "tool_use"
            yield event
        yield RawMessageDeltaEvent(
            type="message_delta",
            delta=Delta(stop_reason=stop_reason, stop_sequence=""),
            usage=MessageDeltaUsage(output_tokens=0),
        )
        yield RawMessageStopEvent(type="message_stop")

    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = lambda **kwargs: mock_generator(
            mock_create.return_value.pop(0), **kwargs
        )

        yield mock_create
