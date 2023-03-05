"""Test init of APCUPSd integration."""
from collections import OrderedDict
from unittest.mock import patch

import pytest

from homeassistant.components.apcupsd import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import CONF_DATA, MOCK_MINIMAL_STATUS, MOCK_STATUS, init_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize("status", (MOCK_STATUS, MOCK_MINIMAL_STATUS))
async def test_async_setup_entry(hass: HomeAssistant, status: OrderedDict) -> None:
    """Test a successful setup entry."""
    # Minimal status does not contain "SERIALNO" field, which is used to determine the
    # unique ID of this integration. But, the integration should work fine without it.
    await init_integration(hass, status=status)

    # Verify successful setup by querying the status sensor.
    state = hass.states.get("binary_sensor.ups_online_status")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "on"


async def test_multiple_integrations(hass: HomeAssistant) -> None:
    """Test successful setup for multiple entries."""
    # Load two integrations from two mock hosts.
    status1 = MOCK_STATUS | {"LOADPCT": "15.0 Percent", "SERIALNO": "XXXXX1"}
    status2 = MOCK_STATUS | {"LOADPCT": "16.0 Percent", "SERIALNO": "XXXXX2"}
    entries = (
        await init_integration(hass, host="test1", status=status1),
        await init_integration(hass, host="test2", status=status2),
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert all(entry.state is ConfigEntryState.LOADED for entry in entries)

    state1 = hass.states.get("sensor.ups_load")
    state2 = hass.states.get("sensor.ups_load_2")
    assert state1 is not None and state2 is not None
    assert state1.state != state2.state


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during integration setup."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA,
        source=SOURCE_USER,
    )

    entry.add_to_hass(hass)

    with patch("apcaccess.status.parse", side_effect=OSError()), patch(
        "apcaccess.status.get"
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_remove(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    # Load two integrations from two mock hosts.
    entries = (
        await init_integration(hass, host="test1", status=MOCK_STATUS),
        await init_integration(hass, host="test2", status=MOCK_MINIMAL_STATUS),
    )

    # Assert they are loaded.
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert all(entry.state is ConfigEntryState.LOADED for entry in entries)

    # Unload the first entry.
    assert await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert entries[0].state is ConfigEntryState.NOT_LOADED
    assert entries[1].state is ConfigEntryState.LOADED

    # Unload the second entry.
    assert await hass.config_entries.async_unload(entries[1].entry_id)
    await hass.async_block_till_done()
    assert all(entry.state is ConfigEntryState.NOT_LOADED for entry in entries)

    # Remove both entries.
    for entry in entries:
        await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
