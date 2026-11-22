"""Tests for the Keenetic NDMS2 diagnostics."""

from unittest.mock import MagicMock

from ndms2_client import Device
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import CLIENT_MAC, MOCK_OPTIONS


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    hass.config_entries.async_update_entry(mock_config_entry, options=MOCK_OPTIONS)
    mock_client.get_devices.return_value = [
        Device(mac=CLIENT_MAC, name="Phone", ip="192.168.1.2", interface="Home"),
        Device(
            mac="11:22:33:44:55:66", name="Laptop", ip="192.168.1.3", interface="Home"
        ),
        Device(mac="22:33:44:55:66:77", name="Server", ip="10.0.0.2", interface="VPS0"),
        # Clients on interfaces that are not tracked are not counted
        Device(
            mac="33:44:55:66:77:88", name="Guest", ip="192.168.2.2", interface="Guest"
        ),
    ]
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
