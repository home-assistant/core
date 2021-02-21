"""Test the SmartTub switch platform."""

from smarttub import SpaPump


async def test_pumps(spa, setup_entry, hass):
    """Test pump entities."""

    for pump in spa.get_pumps.return_value:
        if pump.type == SpaPump.PumpType.CIRCULATION:
            entity_id = f"switch.{spa.brand}_{spa.model}_circulation_pump"
        elif pump.type == SpaPump.PumpType.JET:
            entity_id = f"switch.{spa.brand}_{spa.model}_jet_{pump.id.lower()}"
        else:
            raise NotImplementedError("Unknown pump type")

        state = hass.states.get(entity_id)
        assert state is not None
        if pump.state == SpaPump.PumpState.OFF:
            assert state.state == "off"

            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": entity_id},
                blocking=True,
            )
            pump.toggle.assert_called()
        else:
            assert state.state == "on"

            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": entity_id},
                blocking=True,
            )
            pump.toggle.assert_called()
