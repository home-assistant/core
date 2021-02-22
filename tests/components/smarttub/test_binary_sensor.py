"""Test the SmartTub binary sensor platform."""

from homeassistant.components.binary_sensor import STATE_ON


async def test_binary_sensors(spa, setup_entry, hass):
    """Test the binary sensors."""

    entity_id = f"binary_sensor.{spa.brand}_{spa.model}_online"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
