"""Test init of APCUPSd integration."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.apcupsd.const import DOMAIN
from homeassistant.components.apcupsd.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.util import slugify, utcnow

from . import MOCK_MINIMAL_STATUS, MOCK_STATUS

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize("mock_config_entry", ["mocked-config-entry-id"], indirect=True)
@pytest.mark.parametrize(
    "mock_request_status",
    [
        # Contains "SERIALNO" and "UPSNAME" fields.
        # We should create devices for the entities and prefix their IDs with "MyUPS".
        MOCK_STATUS,
        # Contains "SERIALNO" but no "UPSNAME" field.
        # We should create devices for the entities and prefix their IDs with default "APC UPS".
        MOCK_MINIMAL_STATUS | {"SERIALNO": "XXXX"},
        # Does not contain either "SERIALNO" field or "UPSNAME" field.
        # Our integration should work fine without it by falling back to config entry ID as unique
        # ID and "APC UPS" as the default name.
        MOCK_MINIMAL_STATUS,
        # Some models report "Blank" as SERIALNO, but we should treat it as not reported.
        MOCK_MINIMAL_STATUS | {"SERIALNO": "Blank"},
    ],
    indirect=True,
)
async def test_async_setup_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
    mock_request_status: AsyncMock,
) -> None:
    """Test a successful setup entry."""
    status = mock_request_status.return_value
    entry = init_integration

    identifiers = {(DOMAIN, entry.unique_id or entry.entry_id)}
    device_entry = device_registry.async_get_device(identifiers=identifiers)
    name = f"device_{device_entry.name}_{status.get('SERIALNO', '<no serial>')}"
    assert device_entry == snapshot(name=name)

    platforms = async_get_platforms(hass, DOMAIN)
    assert len(platforms) > 0
    assert all(len(p.entities) > 0 for p in platforms)


@pytest.mark.parametrize(
    "error",
    [OSError(), asyncio.IncompleteReadError(partial=b"", expected=0)],
)
async def test_connection_error(
    hass: HomeAssistant,
    error: Exception,
    mock_config_entry: MockConfigEntry,
    mock_request_status: AsyncMock,
) -> None:
    """Test connection error during integration setup."""
    mock_config_entry.add_to_hass(hass)
    mock_request_status.side_effect = error

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_remove_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful unload and removal of an entry."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED

    # Unload the entry.
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    # Remove the entry.
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_availability(
    hass: HomeAssistant,
    mock_request_status: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Ensure that we mark the entity's availability properly when network is down / back up."""
    device_slug = slugify(mock_request_status.return_value["UPSNAME"])
    state = hass.states.get(f"sensor.{device_slug}_load")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert pytest.approx(float(state.state)) == 14.0

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
