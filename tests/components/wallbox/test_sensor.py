"""Test Wallbox Switch component."""
from homeassistant.const import CONF_ICON, CONF_UNIT_OF_MEASUREMENT, POWER_KILO_WATT
from homeassistant.core import HomeAssistant

from tests.components.wallbox import entry, setup_integration
from tests.components.wallbox.const import (
    MOCK_SENSOR_CHARGING_POWER_ID,
    MOCK_SENSOR_CHARGING_SPEED_ID,
    MOCK_SENSOR_MAX_AVAILABLE_POWER,
)


async def test_wallbox_sensor_class(hass: HomeAssistant) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass)

    state = hass.states.get(MOCK_SENSOR_CHARGING_POWER_ID)
    assert state.attributes[CONF_UNIT_OF_MEASUREMENT] == POWER_KILO_WATT
    assert state.name == "Mock Title Charging Power"

    state = hass.states.get(MOCK_SENSOR_CHARGING_SPEED_ID)
    assert state.attributes[CONF_ICON] == "mdi:speedometer"
    assert state.name == "Mock Title Charging Speed"

    # Test round with precision '0' works
    state = hass.states.get(MOCK_SENSOR_MAX_AVAILABLE_POWER)
    assert state.state == "25.0"

    await hass.config_entries.async_unload(entry.entry_id)
