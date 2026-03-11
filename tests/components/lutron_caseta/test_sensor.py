"""Tests for the Lutron Caseta battery sensor."""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MockBridge, async_setup_integration


async def test_battery_sensor_is_attached_to_shade_device(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the battery sensor is registered under the same shade device."""
    await async_setup_integration(hass, MockBridge)

    cover_entry = entity_registry.async_get("cover.basement_bedroom_left_shade")
    sensor_entry = entity_registry.async_get(
        "sensor.basement_bedroom_left_shade_battery"
    )

    assert cover_entry is not None
    assert sensor_entry is not None
    assert sensor_entry.device_id == cover_entry.device_id


async def test_battery_sensor_updates_on_demand(hass: HomeAssistant) -> None:
    """Test the battery sensor refreshes through Home Assistant's update path."""
    instance = MockBridge()

    def factory(*args: Any, **kwargs: Any) -> MockBridge:
        """Return the mock bridge instance."""
        return instance

    original_get_battery_status = instance.get_battery_status
    instance.get_battery_status = AsyncMock(side_effect=original_get_battery_status)

    await async_setup_integration(hass, factory)
    await hass.async_block_till_done()

    sensor_entity_id = "sensor.basement_bedroom_left_shade_battery"
    initial_state = hass.states.get(sensor_entity_id)
    assert initial_state is not None
    assert initial_state.state == "unknown"

    instance.battery_statuses["802"] = "Low"
    await async_update_entity(hass, sensor_entity_id)
    await hass.async_block_till_done()

    updated_state = hass.states.get(sensor_entity_id)
    assert updated_state is not None
    assert updated_state.state == "Low"
    instance.get_battery_status.assert_awaited_once_with("802")
