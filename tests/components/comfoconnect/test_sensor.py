"""Tests for the comfoconnect sensor platform."""
from homeassistant.helpers import entity_registry as er

from .const import COMPONENT, CONF_DATA as VALID_CONFIG

from tests.common import MockConfigEntry


async def _enable_entity(hass, entity_id: str, entry):
    entity_registry = er.async_get(hass)
    updated_entity = entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()

    assert not updated_entity.disabled


async def test_sensors(hass, mock_bridge_discover, mock_comfoconnect_command):
    """Test the sensors."""
    config_entry = MockConfigEntry(
        domain=COMPONENT,
        data=VALID_CONFIG,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await _enable_entity(hass, "sensor.comfoairq_inside_humidity", config_entry)
    await _enable_entity(hass, "sensor.comfoairq_inside_temperature", config_entry)
    await _enable_entity(hass, "sensor.comfoairq_supply_fan_duty", config_entry)
    await _enable_entity(hass, "sensor.comfoairq_power_usage", config_entry)
    await _enable_entity(hass, "sensor.comfoairq_preheater_energy_total", config_entry)

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test some random sensors after activation
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
