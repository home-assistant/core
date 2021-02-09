"""Tests for the Freedompro sensor."""
from tests.components.freedompro import init_integration


async def test_sensor_get_state(hass):
    """Test states of the sensor."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("sensor.garden_light_sensors")
    assert state
    assert state.state == "500"
    assert state.attributes.get("friendly_name") == "Garden light sensors"

    entry = registry.async_get("sensor.garden_light_sensors")
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*JVRAR_6WVL1Y0PJ5GFWGPMFV7FLVD4MZKBWXC_UFWYM"
    )
