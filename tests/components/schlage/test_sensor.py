"""Test schlage sensor."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant

from . import MockSchlageConfigEntry


async def test_battery_sensor(
    hass: HomeAssistant, mock_added_config_entry: MockSchlageConfigEntry
) -> None:
    """Test the battery sensor."""
    battery_sensor = hass.states.get("sensor.vault_door_battery")
    assert battery_sensor is not None
    assert battery_sensor.state == "20"
    assert battery_sensor.attributes["unit_of_measurement"] == PERCENTAGE
    assert battery_sensor.attributes["device_class"] == SensorDeviceClass.BATTERY
