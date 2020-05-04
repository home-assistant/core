"""Test Z-Wave Sensors."""
from .common import setup_zwave


async def test_sensor(hass, generic_data):
    """Test setting up config entry."""
    await setup_zwave(hass, fixture=generic_data)

    # Test standard sensor
    state = hass.states.get("sensor.smart_plug_electric_v")
    assert state is not None
    assert state.state == "123.9"
    assert state.attributes["unit_of_measurement"] == "V"

    # Test ZWaveListSensor disabled by default
    registry = await hass.helpers.entity_registry.async_get_registry()
    entity_id = "sensor.water_sensor_6_instance_1_water"
    state = hass.states.get(entity_id)
    assert state is None

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == "integration"

    # Test enabling entity
    updated_entry = registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False
