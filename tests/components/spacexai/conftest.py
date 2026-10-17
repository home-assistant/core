"""Fixtures for SpaceXAI tests."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from spacexai_subscription_client import SpaceXAISubscriptionClient

from homeassistant.components.spacexai.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL, CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ACCESS_TOKEN = "access-token"
REFRESH_TOKEN = "refresh-token"


@pytest.fixture
def enable_assist() -> bool:
    """Return whether the conversation agent can control Home Assistant."""
    return False


def _mock_config_entry(enable_assist: bool) -> MockConfigEntry:
    """Return a configured SpaceXAI entry."""
    data = {
        CONF_MODEL: "grok-4.6",
        CONF_PROMPT: "Be helpful.",
    }
    if enable_assist:
        data[CONF_LLM_HASS_API] = [llm.LLM_API_ASSIST]
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home User",
        unique_id="account-123",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN,
                "refresh_token": REFRESH_TOKEN,
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        },
        subentries_data=[
            ConfigSubentryData(
                data=data,
                subentry_id="conversation-subentry",
                subentry_type="conversation",
                title="Grok",
                unique_id=None,
            )
        ],
    )


@pytest.fixture
def mock_config_entry(enable_assist: bool) -> MockConfigEntry:
    """Return a configured SpaceXAI entry."""
    return _mock_config_entry(enable_assist)


@pytest.fixture
def mock_config_entry_with_assist() -> MockConfigEntry:
    """Return a configured SpaceXAI entry with Assist tools enabled."""
    return _mock_config_entry(True)


@pytest.fixture
def mock_spacexai_subscription_client() -> Generator[MagicMock]:
    """Return a mocked SpaceXAI client."""
    client = MagicMock(spec=SpaceXAISubscriptionClient)
    client.async_list_models = AsyncMock(return_value=("grok-4.6",))
    client.async_create_response = AsyncMock()
    with patch(
        "homeassistant.components.spacexai.SpaceXAISubscriptionClient",
        return_value=client,
    ):
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config flows from setting up created entries."""
    with patch(
        "homeassistant.components.spacexai.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant) -> None:
    """Set up the Home Assistant LLM API."""
    assert await async_setup_component(hass, "homeassistant", {})
