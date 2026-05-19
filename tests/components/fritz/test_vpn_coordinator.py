"""Tests for FRITZ!Box Tools WireGuard VPN coordinator."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.components.fritz.vpn_data import FRITZ_VPN_DATA_KEY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry

VPN_CONNECTIONS = {
    "uid-office": {
        "name": "Office",
        "active": True,
        "connected": False,
        "uid": "wg-1",
    }
}


@pytest.fixture
def mock_vpn_session() -> AsyncMock:
    """Mock fritzboxvpn session."""
    session = AsyncMock()
    session.async_get_vpn_connections.return_value = VPN_CONNECTIONS
    session.async_close.return_value = None
    return session


async def test_vpn_coordinator_starts_with_fritz_entry(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    mock_vpn_session: AsyncMock,
) -> None:
    """VPN coordinator is stored separately from AvmWrapper runtime_data."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.vpn_coordinator.FritzBoxVPNSession",
        return_value=mock_vpn_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    vpn_data = hass.data[FRITZ_VPN_DATA_KEY][entry.entry_id]
    assert vpn_data.coordinator.data == VPN_CONNECTIONS
    assert vpn_data.coordinator.get_vpn_status("uid-office") == "enabled"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mock_vpn_session.async_close.assert_called_once()
    assert entry.entry_id not in hass.data.get(FRITZ_VPN_DATA_KEY, {})
