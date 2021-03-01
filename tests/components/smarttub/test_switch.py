"""Test the SmartTub switch platform."""

import pytest


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
