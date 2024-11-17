"""Test init of APCUPSd integration."""

import asyncio
from collections import OrderedDict
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.apcupsd.const import DOMAIN
from homeassistant.components.apcupsd.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify, utcnow

from . import CONF_DATA, MOCK_MINIMAL_STATUS, MOCK_STATUS, async_init_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "status",
    [
        # Contains "SERIALNO" and "UPSNAME" fields.
        # We should create devices for the entities and prefix their IDs with "MyUPS".
        MOCK_STATUS,
        # Contains "SERIALNO" but no "UPSNAME" field.
        # We should create devices for the entities and prefix their IDs with default "APC UPS".
        MOCK_MINIMAL_STATUS | {"SERIALNO": "XXXX"},
        # Does not contain either "SERIALNO" field nor "UPSNAME".
        # "SERIALNO" is used to determine the unique ID of the integration, but the integration
        # should work fine without it.
        # We should _not_ create devices for the entities and their IDs will not have prefixes.
        MOCK_MINIMAL_STATUS,
    ],
)
async def test_async_setup_entry(
    hass: HomeAssistant,
    status: OrderedDict,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a successful setup entry."""
    await async_init_integration(hass, status=status)

    config_entry = await async_init_integration(hass, status=status)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, config_entry.unique_id)}
    )
    if "UPSNAME" in status or "SERIALNO" in status:
        assert (
            device_entry is not None
        ), "device must be created when UPSNAME or SERIALNO is present"
        assert device_entry == snapshot(name=f"device-{device_entry.name}")

    # Use a representative sensor to test (1) if the integration is working, and (2) the entity ID
    # is properly named.
    online_status_sensor = next(
        state
        for state in hass.states.async_all(domain_filter=Platform.BINARY_SENSOR)
        if state.entity_id.startswith(Platform.BINARY_SENSOR)
        and state.entity_id.endswith("online_status")
    )
    assert online_status_sensor.state == STATE_ON
    expected_prefix = slugify(f"{device_entry.name}") + "_" if device_entry else ""
    expected_name = f"{Platform.BINARY_SENSOR}.{expected_prefix}online_status"
    assert online_status_sensor.entity_id == expected_name


async def test_multiple_integrations(hass: HomeAssistant) -> None:
    """Test successful setup for multiple entries."""
    # Load two integrations from two mock hosts.
    status1 = MOCK_STATUS | {"LOADPCT": "15.0 Percent", "SERIALNO": "XXXXX1"}
    status2 = MOCK_STATUS | {"LOADPCT": "16.0 Percent", "SERIALNO": "XXXXX2"}
    entries = (
        await async_init_integration(hass, host="test1", status=status1),
        await async_init_integration(hass, host="test2", status=status2),
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert all(entry.state is ConfigEntryState.LOADED for entry in entries)

    # Since the two UPS device names are the same, we will have to add a "_2" suffix.
    device_slug = slugify(MOCK_STATUS["UPSNAME"])
    state1 = hass.states.get(f"sensor.{device_slug}_load")
    state2 = hass.states.get(f"sensor.{device_slug}_load_2")
    assert state1 is not None and state2 is not None
    assert state1.state != state2.state


async def test_multiple_integrations_different_devices(hass: HomeAssistant) -> None:
    """Test successful setup for multiple entries with different device names."""
    status1 = MOCK_STATUS | {"SERIALNO": "XXXXX1", "UPSNAME": "MyUPS1"}
    status2 = MOCK_STATUS | {"SERIALNO": "XXXXX2", "UPSNAME": "MyUPS2"}
    entries = (
        await async_init_integration(hass, host="test1", status=status1),
        await async_init_integration(hass, host="test2", status=status2),
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert all(entry.state is ConfigEntryState.LOADED for entry in entries)

    # The device names are different, so they are prefixed differently.
    state1 = hass.states.get("sensor.myups1_load")
    state2 = hass.states.get("sensor.myups2_load")
    assert state1 is not None and state2 is not None


@pytest.mark.parametrize(
    "error",
    [OSError(), asyncio.IncompleteReadError(partial=b"", expected=0)],
)
async def test_connection_error(hass: HomeAssistant, error: Exception) -> None:
    """Test connection error during integration setup."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA,
        source=SOURCE_USER,
    )

    entry.add_to_hass(hass)

    with patch("aioapcaccess.request_status", side_effect=error):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_remove_entry(hass: HomeAssistant) -> None:
    """Test successful unload and removal of an entry."""
    # Load two integrations from two mock hosts.
    entries = (
        await async_init_integration(hass, host="test1", status=MOCK_STATUS),
        await async_init_integration(hass, host="test2", status=MOCK_MINIMAL_STATUS),
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


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entity's availability properly when network is down / back up."""
    await async_init_integration(hass)

    device_slug = slugify(MOCK_STATUS["UPSNAME"])
    state = hass.states.get(f"sensor.{device_slug}_load")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert pytest.approx(float(state.state)) == 14.0

    with patch("aioapcaccess.request_status") as mock_request_status:
        # Mock a network error and then trigger an auto-polling event.
        mock_request_status.side_effect = OSError()
        future = utcnow() + UPDATE_INTERVAL
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        # Sensors should be marked as unavailable.
        state = hass.states.get(f"sensor.{device_slug}_load")
        assert state
        assert state.state == STATE_UNAVAILABLE

        # Reset the API to return a new status and update.
        mock_request_status.side_effect = None
        mock_request_status.return_value = MOCK_STATUS | {"LOADPCT": "15.0 Percent"}
        future = future + UPDATE_INTERVAL
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        # Sensors should be online now with the new value.
        state = hass.states.get(f"sensor.{device_slug}_load")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert pytest.approx(float(state.state)) == 15.0
