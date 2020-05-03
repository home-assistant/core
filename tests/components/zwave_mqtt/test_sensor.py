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
