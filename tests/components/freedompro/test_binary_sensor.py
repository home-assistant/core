"""Tests for the Freedompro binary sensor."""
from tests.components.freedompro import init_integration


async def test_binary_sensor_get_state(hass):
    """Test states of the sensor."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("binary_sensor.doorway_motion_sensor")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Doorway motion sensor"

    entry = registry.async_get("binary_sensor.doorway_motion_sensor")
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*VTEPEDYE8DXGS8U94CJKQDLKMN6CUX1IJWSOER2HZCK"
    )
