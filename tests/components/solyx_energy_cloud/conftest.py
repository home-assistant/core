"""Fixtures and helpers for the Solyx Energy tests."""

from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_array_fixture
from solyx_energy_api.client import SolyxEnergyApiClient

from homeassistant.components.solyx_energy_cloud.const import (
    CONF_NYMO_CLIENT_ID,
    CONF_NYMO_CLIENT_SECRET,
    DOMAIN,
)

from .const import NYMO_CLIENT_ID, NYMO_CLIENT_SECRET

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for the Solyx Energy integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=NYMO_CLIENT_ID,
        data={
            CONF_NYMO_CLIENT_ID: NYMO_CLIENT_ID,
            CONF_NYMO_CLIENT_SECRET: NYMO_CLIENT_SECRET,
        },
        title="Solyx Energy Cloud",
    )


@pytest.fixture
def mock_solyx_api_client() -> AsyncMock:
    """Return a mocked SolyxEnergyApiClient instance."""
    data = load_json_array_fixture("assets_data.json", DOMAIN)
    client = AsyncMock(spec=SolyxEnergyApiClient)
    client.async_get_assets.return_value = data
    client.async_test_connection.return_value = None
    return client


@pytest.fixture
def mock_api_client_class(mock_solyx_api_client: AsyncMock) -> Generator[AsyncMock]:
    """Patch SolyxEnergyApiClient so integration setup and config flow use the mock."""
    with (
        patch(
            "homeassistant.components.solyx_energy_cloud.SolyxEnergyApiClient",
            return_value=mock_solyx_api_client,
        ),
        patch(
            "homeassistant.components.solyx_energy_cloud.config_flow.SolyxEnergyApiClient",
            return_value=mock_solyx_api_client,
        ),
    ):
        yield mock_solyx_api_client


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry, preventing full integration setup."""
    with patch(
        "homeassistant.components.solyx_energy_cloud.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_api_client_class: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Solyx Energy integration and return the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
