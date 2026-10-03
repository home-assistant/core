"""Fixtures for Mistral AI tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.mistral_ai.const import (
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    MISTRAL_MODELS,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


class FakeModels:
    """Minimal stand-in for the models sub-SDK."""

    def list(self, timeout_ms: int | None = None) -> list:
        """Return an empty model list."""
        return []


class FakeCloudClient:
    """Minimal stand-in for the Mistral client used by the conversation entity."""

    def __init__(self) -> None:
        """Initialize the fake client."""
        self.models = FakeModels()
        self.chat = AsyncMock()
        self.chat.stream_async = AsyncMock()


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up the homeassistant component (exposed entities registry)."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
def mock_fetch_models() -> Generator[None]:
    """Patch model fetching so no test hits the real Mistral API."""
    with patch(
        "homeassistant.components.mistral_ai.config_flow._async_fetch_models",
        new_callable=AsyncMock,
        return_value=MISTRAL_MODELS,
    ):
        yield


@pytest.fixture
def mock_client() -> FakeCloudClient:
    """Return a fake Mistral client."""
    return FakeCloudClient()


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry with a conversation subentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mistral",
        data={CONF_API_KEY: "test-key"},
        version=2,
        subentries_data=[
            {
                "subentry_type": "conversation",
                "data": RECOMMENDED_CONVERSATION_OPTIONS,
                "title": DEFAULT_CONVERSATION_NAME,
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
    """Return a config entry with the Assist API enabled."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={CONF_LLM_HASS_API: llm.LLM_API_ASSIST},
    )
    return mock_config_entry


@pytest.fixture
async def mock_init_component(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: FakeCloudClient,
) -> AsyncGenerator[None]:
    """Set up the Mistral AI integration with a fake client."""
    with patch(
        "homeassistant.components.mistral_ai._setup_client",
        return_value=mock_client,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield
