"""Fixtures and helpers for the Solyx Energy tests."""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.solyx_energy.api import SolyxEnergyApiClient
from homeassistant.components.solyx_energy.const import (
    CONF_NYMO_CLIENT_ID,
    CONF_NYMO_CLIENT_SECRET,
    CONF_NYMO_DEVICE_ID,
    DOMAIN,
)
from homeassistant.util.json import json_loads

from .const import NYMO_CLIENT_ID, NYMO_CLIENT_SECRET, NYMO_DEVICE_ID

from tests.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for the Solyx Energy integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=NYMO_DEVICE_ID,
        data={
            CONF_NYMO_CLIENT_ID: NYMO_CLIENT_ID,
            CONF_NYMO_CLIENT_SECRET: NYMO_CLIENT_SECRET,
            CONF_NYMO_DEVICE_ID: NYMO_DEVICE_ID,
        },
        title=f"Nymo {NYMO_DEVICE_ID}",
    )


@pytest.fixture
def mock_solyx_api_client():
    """Return a mocked SolyxEnergyApiClient instance."""
    data = json_loads((FIXTURES_DIR / "asset_data.json").read_text())
    client = AsyncMock(spec=SolyxEnergyApiClient)
    client.async_get_asset_data.return_value = data
    client.async_set_asset_attribute.return_value = None
    client.async_test_connection.return_value = None
    return client


@pytest.fixture
def mock_api_client_class(mock_solyx_api_client):
    """Patch SolyxEnergyApiClient so integration setup and config flow use the mock."""
    with (
        patch(
            "homeassistant.components.solyx_energy.SolyxEnergyApiClient",
            return_value=mock_solyx_api_client,
        ),
        patch(
            "homeassistant.components.solyx_energy.config_flow.SolyxEnergyApiClient",
            return_value=mock_solyx_api_client,
        ),
    ):
        yield mock_solyx_api_client


@pytest.fixture
def mock_setup_entry():
    """Mock setting up a config entry, preventing full integration setup."""
    with patch(
        "homeassistant.components.solyx_energy.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_api_client_class, mock_config_entry
):
    """Set up the Solyx Energy integration and return the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
