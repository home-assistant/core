"""Provide tests for mysensors sensor platform."""


async def test_gps_sensor(hass, gps_sensor, integration):
    """Test a gps sensor."""
    entity_id = "sensor.gps_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state.state == "40.741894,-73.989311,12"
