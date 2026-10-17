"""Fixtures for the Open Responses integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from openresponses_client import BadRequestError, Response
from openresponses_client.models import (
    ResponseCompletedEvent,
    ResponseOutputTextDeltaEvent,
    Usage,
)
import pytest

from homeassistant.components.openresponses.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LLM_HASS_API,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from . import MockStream

from tests.common import MockConfigEntry

TEST_URL = "http://localhost:8080/v1"
TEST_MODEL = "gpt-oss:20b"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.openresponses.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def conversation_subentry_data() -> dict[str, Any]:
    """Return the conversation subentry data."""
    return {
        CONF_MODEL: TEST_MODEL,
        CONF_PROMPT: "You are a helpful assistant.",
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    }


@pytest.fixture
def mock_config_entry(conversation_subentry_data: dict[str, Any]) -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        title="localhost",
        domain=DOMAIN,
        data={CONF_URL: TEST_URL, CONF_API_KEY: "sk-test"},
        subentries_data=[
            ConfigSubentryData(
                data=conversation_subentry_data,
                subentry_id="ulid-conversation",
                subentry_type="conversation",
                title=TEST_MODEL,
                unique_id=None,
            )
        ],
    )


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the Open Responses client."""
    with (
        patch(
            "homeassistant.components.openresponses.OpenResponsesClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.openresponses.config_flow.OpenResponsesClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.create.side_effect = BadRequestError("Missing model", status=400)
        client.stream.return_value = MockStream(
            [
                ResponseOutputTextDeltaEvent(delta="Hello, "),
                ResponseOutputTextDeltaEvent(delta="how can I help?"),
                ResponseCompletedEvent(
                    response=Response(usage=Usage(input_tokens=8, output_tokens=5))
                ),
            ]
        )
        yield client


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> MockConfigEntry:
    """Set up the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
