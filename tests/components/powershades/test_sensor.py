"""Tests for the PowerShades sensor platform."""

from homeassistant.components.powershades.protocol import battery_percentage
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_sensors_disabled_by_default(hass: HomeAssistant, config_entry) -> None:
    """Battery and voltage sensors are registered but disabled by default."""
    registry = er.async_get(hass)

    battery_entry = registry.async_get("sensor.powershade_bedroom_shade_battery")
    voltage_entry = registry.async_get("sensor.powershade_bedroom_shade_voltage")

    assert battery_entry is not None
    assert battery_entry.disabled
    assert voltage_entry is not None
    assert voltage_entry.disabled


async def test_sensor_values_when_enabled(hass: HomeAssistant, config_entry) -> None:
    """Once enabled, the sensors report the battery percentage and voltage."""
    registry = er.async_get(hass)

    for object_id in ("battery", "voltage"):
        registry.async_update_entity(
            f"sensor.powershade_bedroom_shade_{object_id}", disabled_by=None
        )

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    voltage_state = hass.states.get("sensor.powershade_bedroom_shade_voltage")
    battery_state = hass.states.get("sensor.powershade_bedroom_shade_battery")

    assert voltage_state.state == "3700"
    assert battery_state.state == str(battery_percentage(3700))
