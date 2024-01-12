"""Test System Monitor sensor."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant


async def test_sensor(
    hass: HomeAssistant, mock_added_config_entry: ConfigEntry
) -> None:
    """Test the sensor."""
    memory_sensor = hass.states.get("sensor.system_monitor_memory_free")
    assert memory_sensor is not None
    assert memory_sensor.state == "40.0"

    process_sensor = hass.states.get("sensor.system_monitor_process_python3")
    assert process_sensor is not None
    assert process_sensor.state == STATE_ON
