"""Tests for the Roomba diagnostics."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_roomba.master_state["state"]["reported"]["netinfo"] = {
        "dhcp": True,
        "addr": 3232235550,
        "mask": 4294967040,
        "gw": 3232235521,
        "dns1": 3232235521,
        "dns2": 0,
        "bssid": "aa:bb:cc:dd:ee:00",
        "sec": 4,
    }
    mock_roomba.master_state["state"]["reported"]["wlcfg"] = {
        "sec": 7,
        "ssid": "4D7957694669",
    }
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
