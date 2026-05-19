"""Pytest fixtures for FritzBox VPN tests."""

import pytest

from homeassistant.components.fritzbox_vpn.coordinator import FritzBoxVPNCoordinator
from homeassistant.components.fritzbox_vpn.models import FritzboxVpnRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .fixtures import MOCK_VPN_CONNECTIONS

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Configured FritzBox VPN entry."""
    return MockConfigEntry(
        domain="fritzbox_vpn",
        data={
            "host": "192.168.178.1",
            "username": "user",
            "password": "pass",
        },
        title="FritzBox VPN",
    )


@pytest.fixture
async def coordinator_with_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> FritzBoxVPNCoordinator:
    """Coordinator on entry.runtime_data with VPN sample data."""
    mock_config_entry.add_to_hass(hass)
    coordinator = FritzBoxVPNCoordinator(
        hass,
        mock_config_entry.data,
        mock_config_entry.options,
        mock_config_entry.entry_id,
    )
    coordinator.async_set_updated_data(MOCK_VPN_CONNECTIONS)
    mock_config_entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    return coordinator
