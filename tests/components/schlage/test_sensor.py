"""Test schlage sensor."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


async def test_sensor_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_added_config_entry: ConfigEntry,
) -> None:
    """Test sensor is added to device registry."""
    device = device_registry.async_get_device(identifiers={("schlage", "test")})
    assert device.model == "<model-name>"
    assert device.sw_version == "1.0"
    assert device.name == "Vault Door"
    assert device.manufacturer == "Schlage"


async def test_battery_sensor(
    hass: HomeAssistant, mock_added_config_entry: ConfigEntry
) -> None:
    """Test the battery sensor."""
    battery_sensor = hass.states.get("sensor.vault_door_battery")
    assert battery_sensor is not None
    assert battery_sensor.state == "20"
    assert battery_sensor.attributes["unit_of_measurement"] == PERCENTAGE
    assert battery_sensor.attributes["device_class"] == SensorDeviceClass.BATTERY
