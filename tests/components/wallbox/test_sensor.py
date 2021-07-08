"""Test Wallbox Switch component."""

from tests.components.wallbox import entry, setup_integration


async def test_wallbox_sensor_class(hass):
    """Test wallbox sensor class."""

    await setup_integration(hass)

    state = hass.states.get("sensor.mock_title_charging_power")
    assert state.attributes["unit_of_measurement"] == "kW"
    assert state.name == "Mock Title Charging Power"

    state = hass.states.get("sensor.mock_title_charging_speed")
    assert state.attributes["icon"] == "mdi:speedometer"
    assert state.name == "Mock Title Charging Speed"

    await hass.config_entries.async_unload(entry.entry_id)
