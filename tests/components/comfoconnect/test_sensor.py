"""Tests for the comfoconnect sensor platform."""
import pytest


@pytest.fixture
async def setup_sensor(mock_bridge, mock_comfoconnect_command, mock_config_entry, hass):
    """Set up demo sensor component."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors(setup_sensor, hass):
    """Test the sensors."""
    state = hass.states.get("sensor.comfoairq_inside_humidity")
    assert state is not None
    assert state.name == "ComfoAirQ Inside humidity"
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("device_class") == "humidity"
    assert state.attributes.get("icon") is None

    state = hass.states.get("sensor.comfoairq_inside_temperature")
    assert state is not None
    assert state.name == "ComfoAirQ Inside temperature"
    assert state.attributes.get("unit_of_measurement") == "°C"
    assert state.attributes.get("device_class") == "temperature"
    assert state.attributes.get("icon") is None

    state = hass.states.get("sensor.comfoairq_supply_fan_duty")
    assert state is not None
    assert state.name == "ComfoAirQ Supply fan duty"
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("icon") == "mdi:fan-plus"

    state = hass.states.get("sensor.comfoairq_power_usage")
    assert state is not None
    assert state.name == "ComfoAirQ Power usage"
    assert state.attributes.get("unit_of_measurement") == "W"
    assert state.attributes.get("device_class") == "power"
    assert state.attributes.get("icon") is None

    state = hass.states.get("sensor.comfoairq_preheater_energy_total")
    assert state is not None
    assert state.name == "ComfoAirQ Preheater energy total"
    assert state.attributes.get("unit_of_measurement") == "kWh"
    assert state.attributes.get("device_class") == "energy"
    assert state.attributes.get("icon") is None
