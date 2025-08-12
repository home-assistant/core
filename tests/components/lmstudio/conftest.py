"""Common fixtures for the LM Studio tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.homeassistant.exposed_entities import (
    DATA_EXPOSED_ENTITIES,
)
from homeassistant.components.lmstudio.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_LLM_HASS_API, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def setup_exposed_entities(hass: HomeAssistant):
    """Set up exposed entities data for conversation component."""

    # Mock the exposed entities manager
    mock_manager = Mock()
    mock_manager.async_should_expose = Mock(return_value=False)
    hass.data[DATA_EXPOSED_ENTITIES] = mock_manager


MOCK_USER_INPUT = {
    "base_url": "http://localhost:1234/v1",
    "api_key": "test-key",
}

MOCK_OPTIONS = {
    CONF_NAME: "Test LM Studio",
    "model": "test-model",
    "max_tokens": 100,
    "temperature": 0.7,
    "top_p": 1.0,
    CONF_LLM_HASS_API: False,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""

    return MockConfigEntry(
        title="LM Studio",
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        options=MOCK_OPTIONS,
        subentries_data=[
            ConfigSubentryData(
                title="LM Studio Conversation",
                data={
                    CONF_NAME: "LM Studio Conversation",
                    "model": "test-model",
                    "max_tokens": 100,
                    "temperature": 0.7,
                    "top_p": 1.0,
                    CONF_LLM_HASS_API: False,
                },
                subentry_id="conversation_1",
                subentry_type="conversation",
                unique_id="conversation_1",
            ),
            ConfigSubentryData(
                title="LM Studio AI",
                data={
                    CONF_NAME: "LM Studio AI",
                    "model": "test-model",
                    "max_tokens": 500,
                    "temperature": 0.3,
                    "top_p": 0.95,
                },
                subentry_id="ai_task_1",
                subentry_type="ai_task_data",
                unique_id="ai_task_1",
            ),
        ],
    )


@pytest.fixture
def mock_openai_client() -> Generator[AsyncMock]:
    """Mock the OpenAI client."""
    mock_models = Mock()
    mock_models.data = [
        Mock(id="test-model"),
        Mock(id="another-model"),
    ]

    with patch(
        "homeassistant.components.lmstudio.config_flow.openai.AsyncOpenAI"
    ) as mock_client:
        mock_instance = AsyncMock()
        # Set up the mock to properly mimic OpenAI client behavior
        mock_instance.with_options = Mock()  # with_options is synchronous
        mock_with_options_result = Mock()
        mock_with_options_result.models = Mock()
        mock_with_options_result.models.list = AsyncMock(return_value=mock_models)
        mock_instance.with_options.return_value = mock_with_options_result
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_openai_client_config_flow() -> Generator[AsyncMock]:
    """Mock the OpenAI client for config flow tests."""
    mock_models = Mock()
    mock_models.data = [
        Mock(id="test-model"),
        Mock(id="another-model"),
    ]

    with (
        patch(
            "homeassistant.components.lmstudio.config_flow.openai.AsyncOpenAI"
        ) as mock_client,
        patch(
            "homeassistant.components.lmstudio.entity.openai.AsyncOpenAI"
        ) as mock_entity_client,
        patch(
            "homeassistant.components.lmstudio.openai.AsyncOpenAI"
        ) as mock_init_client,
    ):
        mock_instance = AsyncMock()
        # Set up the mock to properly mimic OpenAI client behavior
        mock_instance.with_options = Mock()  # with_options is synchronous
        mock_with_options_result = Mock()
        mock_with_options_result.models = Mock()
        mock_with_options_result.models.list = AsyncMock(return_value=mock_models)
        mock_instance.with_options.return_value = mock_with_options_result

        mock_instance.chat.completions.create.return_value = AsyncMock(
            choices=[AsyncMock(message=AsyncMock(content="Test response"))]
        )

        mock_client.return_value = mock_instance
        mock_entity_client.return_value = mock_instance
        mock_init_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client_config_flow: AsyncMock,
) -> MockConfigEntry:
    """Set up the LM Studio integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
