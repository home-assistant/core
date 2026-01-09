"""Tests helpers."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_USE_GOOGLE_SEARCH_TOOL,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_TTS_NAME,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TTS_OPTIONS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="google_generative_ai_conversation",
        title="Google Generative AI Conversation",
        data={
            "api_key": "bla",
        },
        version=2,
        minor_version=3,
        subentries_data=[
            {
                "data": RECOMMENDED_CONVERSATION_OPTIONS,
                "subentry_type": "conversation",
                "title": DEFAULT_CONVERSATION_NAME,
                "subentry_id": "ulid-conversation",
                "unique_id": None,
            },
            {
                "data": RECOMMENDED_STT_OPTIONS,
                "subentry_type": "stt",
                "title": DEFAULT_STT_NAME,
                "subentry_id": "ulid-stt",
                "unique_id": None,
            },
            {
                "data": RECOMMENDED_TTS_OPTIONS,
                "subentry_type": "tts",
                "title": DEFAULT_TTS_NAME,
                "subentry_id": "ulid-tts",
                "unique_id": None,
            },
            {
                "data": RECOMMENDED_AI_TASK_OPTIONS,
                "subentry_type": "ai_task_data",
                "title": DEFAULT_AI_TASK_NAME,
                "subentry_id": "ulid-ai-task",
                "unique_id": None,
            },
        ],
    )
    entry.runtime_data = Mock()
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_config_entry_with_assist(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_genai_client: AsyncMock,
) -> MockConfigEntry:
    """Mock a config entry with assist."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={CONF_LLM_HASS_API: llm.LLM_API_ASSIST},
    )
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
async def mock_config_entry_with_google_search(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_genai_client: AsyncMock,
) -> MockConfigEntry:
    """Mock a config entry with assist."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
            CONF_USE_GOOGLE_SEARCH_TOOL: True,
        },
    )
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
async def mock_init_component(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_genai_client: AsyncMock
) -> AsyncGenerator[None]:
    """Initialize integration."""
    assert await async_setup_component(hass, "google_generative_ai_conversation", {})
    await hass.async_block_till_done()
    yield


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def mock_genai_client() -> Generator[AsyncMock]:
    """Mock the client."""
    with patch(
        "homeassistant.components.google_generative_ai_conversation.Client",
        autospec=True,
    ) as mock_client:
        mock_client.return_value.aio.models.generate_content_stream = AsyncMock()
        mock_client.return_value.aio.models.generate_content = AsyncMock()
        mock_client.return_value.aio.models.get = AsyncMock()
        yield mock_client.return_value
