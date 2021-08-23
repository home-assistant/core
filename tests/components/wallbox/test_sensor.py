"""Test Wallbox Switch component."""
from homeassistant.const import CONF_ICON, CONF_UNIT_OF_MEASUREMENT, POWER_KILO_WATT

from tests.components.wallbox import entry, setup_integration
from tests.components.wallbox.const import (
    CONF_MOCK_SENSOR_CHARGING_POWER_ID,
    CONF_MOCK_SENSOR_CHARGING_SPEED_ID,
)


async def test_wallbox_sensor_class(hass):
    """Test wallbox sensor class."""

    await setup_integration(hass)

    state = hass.states.get(CONF_MOCK_SENSOR_CHARGING_POWER_ID)
    assert state.attributes[CONF_UNIT_OF_MEASUREMENT] == POWER_KILO_WATT
    assert state.name == "Mock Title Charging Power"

    state = hass.states.get(CONF_MOCK_SENSOR_CHARGING_SPEED_ID)
    assert state.attributes[CONF_ICON] == "mdi:speedometer"
    assert state.name == "Mock Title Charging Speed"

    await hass.config_entries.async_unload(entry.entry_id)
