"""Test the SmartTub switch platform."""

from . import trigger_update


async def test_switch(spa, setup_entry, hass, smarttub_api):
    """Test the switch entity."""

    entity_id = f"switch.{spa.brand}_{spa.model}_circulation_pump"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"
