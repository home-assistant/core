"""Tests for the Lutron Caseta binary sensors."""

from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.lutron_caseta.binary_sensor import SCAN_INTERVAL
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration

from tests.common import async_fire_time_changed


class SingleSubscriberMockBridge(MockBridge):
    """Mock bridge that matches pylutron-caseta's device subscriber behavior."""

    def add_subscriber(self, device_id: str, callback_: Any) -> None:
        """Mock a listener to be notified of state changes."""
        self._subscribers[device_id] = callback_

    def call_subscribers(self, device_id: str) -> None:
        """Notify subscribers of a device state change."""
        if callback := self._subscribers.get(device_id):
            callback()


async def test_battery_sensor_is_attached_to_shade_device(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the battery sensor is registered under the same shade device."""
    await async_setup_integration(hass, MockBridge)

    cover_entry = entity_registry.async_get("cover.basement_bedroom_left_shade")
    binary_sensor_entry = entity_registry.async_get(
        "binary_sensor.basement_bedroom_left_shade_battery"
    )

    assert cover_entry is not None
    assert binary_sensor_entry is not None
    assert binary_sensor_entry.device_id == cover_entry.device_id


async def test_battery_sensor_does_not_replace_shade_subscriber(
    hass: HomeAssistant,
) -> None:
    """Test the battery sensor does not replace the cover subscriber."""
    instance = SingleSubscriberMockBridge()

    def factory(*args: Any, **kwargs: Any) -> MockBridge:
        """Return the mock bridge instance."""
        return instance

    await async_setup_integration(hass, factory)
    await hass.async_block_till_done()

    cover_entity_id = "cover.basement_bedroom_left_shade"
    instance.devices["802"]["current_state"] = 50
    instance.call_subscribers("802")
    await hass.async_block_till_done()

    state = hass.states.get(cover_entity_id)
    assert state is not None
    assert state.state == "open"
    assert state.attributes["current_position"] == 50


async def test_battery_sensor_updates_on_schedule(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the battery sensor refreshes naturally on its polling interval."""
    instance = MockBridge()

    def factory(*args: Any, **kwargs: Any) -> MockBridge:
        """Return the mock bridge instance."""
        return instance

    original_get_battery_status = instance.get_battery_status
    instance.get_battery_status = AsyncMock(side_effect=original_get_battery_status)

    await async_setup_integration(hass, factory)
    await hass.async_block_till_done()

    binary_sensor_entity_id = "binary_sensor.basement_bedroom_left_shade_battery"
    initial_state = hass.states.get(binary_sensor_entity_id)
    assert initial_state is not None
    assert initial_state.state == STATE_OFF
    assert initial_state.name == "Basement Bedroom Left Shade Battery"
    assert (
        initial_state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.BATTERY
    )

    instance.battery_statuses["802"] = " Low "
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    updated_state = hass.states.get(binary_sensor_entity_id)
    assert updated_state is not None
    assert updated_state.state == STATE_ON
    assert instance.get_battery_status.await_count == 2
    instance.get_battery_status.assert_awaited_with("802")

    instance.battery_statuses["802"] = "Unknown"
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    unknown_state = hass.states.get(binary_sensor_entity_id)
    assert unknown_state is not None
    assert unknown_state.state == STATE_UNKNOWN
    assert instance.get_battery_status.await_count == 3
