"""Test the SmartTub switch platform."""

import pytest

from homeassistant.const import STATE_OFF, STATE_ON


@pytest.mark.parametrize(
    "pump_id,entity_suffix,pump_state",
    [
        ("CP", "circulation_pump", "off"),
        ("P1", "jet_p1", "off"),
        ("P2", "jet_p2", "on"),
    ],
)
async def test_pumps(spa, setup_entry, hass, pump_id, pump_state, entity_suffix):
    """Test pump entities."""

    pump = next(pump for pump in await spa.get_pumps() if pump.id == pump_id)

    entity_id = f"switch.{spa.brand}_{spa.model}_{entity_suffix}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == pump_state

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": entity_id},
        blocking=True,
    )
    pump.toggle.assert_called()

    if state.state == STATE_OFF:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )
        pump.toggle.assert_called()
    else:
        assert state.state == STATE_ON

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )
        pump.toggle.assert_called()
