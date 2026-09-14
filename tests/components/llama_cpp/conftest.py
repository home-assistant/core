"""Fixtures for llama.cpp integration tests."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass, field
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.llama_cpp.const import (
    CONF_BASE_URL,
    DEFAULT_BASE_URL,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import chat_session, llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

CONFIG_ENTRY_DATA = {
    CONF_API_KEY: "sk-0000000000000000000",
    CONF_BASE_URL: DEFAULT_BASE_URL,
}
ASSIST_OPTIONS = {CONF_LLM_HASS_API: llm.LLM_API_ASSIST}


@pytest.fixture(autouse=True)
async def setup_home_assistant(hass: HomeAssistant) -> None:
    """Enable dependencies."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture(name="platforms")
def mock_platforms() -> list[Platform]:
    """Fixture for platforms loaded by the integration."""
    return []


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> AsyncGenerator[None]:
    """Set up the integration."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="config_entry_data")
def config_entry_data_fixture() -> dict[str, Any]:
    """Fixture to add data to the config entry."""
    return {}


@pytest.fixture(name="config_entry_options")
def config_entry_options_fixture() -> dict[str, Any]:
    """Fixture to add options to the config entry."""
    return {}


@pytest.fixture(name="mock_config_entry")
def mock_config_entry_fixture(
    hass: HomeAssistant,
    config_entry_data: dict[str, Any],
    config_entry_options: dict[str, Any],
) -> MockConfigEntry:
    """Fixture to create a configuration entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="llama.cpp",
        data={
            **CONFIG_ENTRY_DATA,
            **config_entry_data,
        },
        version=1,
        minor_version=1,
        subentries_data=[
            ConfigSubentryData(
                data={**config_entry_options},
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
        ],
    )
    config_entry.add_to_hass(hass)
    return config_entry


@dataclass
class MockChatLog(conversation.ChatLog):
    """Mock chat log."""

    _mock_tool_results: dict[str, Any] = field(default_factory=dict)

    def mock_tool_results(self, results: dict[str, Any]) -> None:
        """Set tool results."""
        self._mock_tool_results = results

    @property
    def llm_api(self) -> llm.APIInstance | None:
        """Return LLM API."""
        return self._llm_api

    @llm_api.setter
    def llm_api(self, value: llm.APIInstance | None) -> None:
        """Set LLM API."""
        self._llm_api = value

        if not value:
            return

        async def async_call_tool(tool_input: llm.ToolInput) -> llm.ToolResult:
            """Call tool."""
            if tool_input.id not in self._mock_tool_results:
                raise ValueError(
                    f"Tool {tool_input.id} not found ({self._mock_tool_results})"
                )
            return self._mock_tool_results[tool_input.id]

        self._llm_api.async_call_tool = async_call_tool


@pytest.fixture
def mock_chat_log(hass: HomeAssistant) -> Generator[conversation.ChatLog]:
    """Return mock chat logs."""
    # pylint: disable-next=contextmanager-generator-missing-cleanup
    with (
        patch(
            "homeassistant.components.conversation.chat_log.ChatLog",
            MockChatLog,
        ),
        chat_session.async_get_chat_session(hass, "mock-conversation-id") as session,
        conversation.async_get_chat_log(hass, session) as chat_log,
    ):
        yield chat_log


@pytest.fixture(autouse=True)
def mock_models_list() -> Generator[AsyncMock]:
    """Initialize integration."""
    with patch(
        "openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
    ) as mock_list:
        yield mock_list


@pytest.fixture(name="mock_completion", autouse=True)
def mock_openai_client_fixture() -> Generator[AsyncMock]:
    """Fixture to mock the OpenAI client."""
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
    ) as mock_create:
        yield mock_create
