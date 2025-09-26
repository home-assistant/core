"""Test cases for the switcher_kis component."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.switcher_kis.const import DOMAIN, MAX_UPDATE_INTERVAL_SEC
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify

from . import init_integration
from .consts import DUMMY_DEVICE_ID1, DUMMY_DEVICE_ID4, DUMMY_SWITCHER_DEVICES

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator


async def test_update_fail(
    hass: HomeAssistant,
    mock_bridge,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities state unavailable when updates fail.."""
    entry = await init_integration(hass)
    assert mock_bridge

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 2

    freezer.tick(timedelta(seconds=MAX_UPDATE_INTERVAL_SEC + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for device in DUMMY_SWITCHER_DEVICES:
        assert (
            f"Device {device.name} did not send update for {MAX_UPDATE_INTERVAL_SEC} seconds"
            in caplog.text
        )

        entity_id = f"switch.{slugify(device.name)}"
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

        entity_id = f"sensor.{slugify(device.name)}_power"
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=MAX_UPDATE_INTERVAL_SEC - 2)
    )
    await hass.async_block_till_done()

    for device in DUMMY_SWITCHER_DEVICES:
        entity_id = f"switch.{slugify(device.name)}"
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE

        entity_id = f"sensor.{slugify(device.name)}_power"
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE


async def test_entry_unload(hass: HomeAssistant, mock_bridge) -> None:
    """Test entry unload."""
    entry = await init_integration(hass)
    assert mock_bridge

    assert entry.state is ConfigEntryState.LOADED
    assert mock_bridge.is_running is True

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert mock_bridge.is_running is False


async def test_remove_device(
    hass: HomeAssistant,
    mock_bridge,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test being able to remove a disconnected device."""
    assert await async_setup_component(hass, "config", {})
    entry = await init_integration(hass)
    entry_id = entry.entry_id
    assert mock_bridge

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 2

    live_device_id = DUMMY_DEVICE_ID1
    dead_device_id = DUMMY_DEVICE_ID4

    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2

    # Create a dead device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, dead_device_id)},
        manufacturer="Switcher",
        model="Switcher Model",
        name="Switcher Device",
    )
    await hass.async_block_till_done()
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 3

    # Try to remove a live device - fails
    device = device_registry.async_get_device(identifiers={(DOMAIN, live_device_id)})
    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id, entry_id)
    assert not response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 3
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, live_device_id)})
        is not None
    )

    # Try to remove a dead device - succeeds
    device = device_registry.async_get_device(identifiers={(DOMAIN, dead_device_id)})
    response = await client.remove_device(device.id, entry_id)
    assert response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, dead_device_id)}) is None
    )
