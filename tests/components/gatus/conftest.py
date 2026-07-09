"""Common fixtures for the Gatus tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gatus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_gatus_client() -> Generator[AsyncMock]:
    """Mock the third-party Gatus API client wrapper globally across coordinator and config flow."""
    with (
        patch(
            "homeassistant.components.gatus.coordinator.GatusClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.gatus.config_flow.GatusClient",
            new=mock_client,
        ),
    ):
        client_instance = mock_client.return_value
        client_instance.get_endpoints_statuses = AsyncMock(
            return_value=[
                {
                    "key": "backend_service",
                    "name": "Backend Service",
                    "group": "Core",
                    "results": [{"success": True, "status": 200}],
                }
            ]
        )
        yield client_instance


@pytest.fixture
async def mock_config_entry(
    hass: HomeAssistant, mock_gatus_client: AsyncMock
) -> MockConfigEntry:
    """Fixture to cleanly set up and initialize a Gatus configuration entry inside Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus.example.com:8080"},
        entry_id="1234567890abcdef1234567890abcdef",
    )
    await setup_integration(hass, entry)

    return entry
