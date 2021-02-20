"""Test the SmartTub sensor platform."""

from . import trigger_update


async def test_state_update(spa, setup_entry, hass, smarttub_api):
    """Test the state entity."""

    entity_id = f"sensor.{spa.brand}_{spa.model}_state"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "normal"

    spa.get_status.return_value["state"] = "BAD"
    await trigger_update(hass)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "bad"
