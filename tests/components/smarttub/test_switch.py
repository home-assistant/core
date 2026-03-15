"""Test the SmartTub switch platform."""

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("pump_id", "entity_suffix", "expected_state"),
    [
        ("CP", "circulation_pump", STATE_OFF),
        ("P1", "jet_p1", STATE_OFF),
        ("P2", "jet_p2", STATE_ON),
    ],
)
async def test_pump_state(
    spa, setup_entry, hass: HomeAssistant, pump_id, entity_suffix, expected_state
) -> None:
    """Test pump entity initial state."""
    entity_id = f"switch.{spa.brand}_{spa.model}_{entity_suffix}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("pump_id", "entity_suffix"),
    [
        ("CP", "circulation_pump"),
        ("P1", "jet_p1"),
        ("P2", "jet_p2"),
    ],
)
async def test_pump_toggle(
    spa, setup_entry, hass: HomeAssistant, pump_id, entity_suffix
) -> None:
    """Test toggling a pump."""
    status = await spa.get_status_full()
    pump = next(pump for pump in status.pumps if pump.id == pump_id)
    entity_id = f"switch.{spa.brand}_{spa.model}_{entity_suffix}"

    await hass.services.async_call(
        "switch", "toggle", {"entity_id": entity_id}, blocking=True
    )
    pump.toggle.assert_called()


@pytest.mark.parametrize(
    ("pump_id", "entity_suffix"),
    [
        ("CP", "circulation_pump"),
        ("P1", "jet_p1"),
    ],
)
async def test_pump_turn_on(
    spa, setup_entry, hass: HomeAssistant, pump_id, entity_suffix
) -> None:
    """Test turning on an off pump toggles it."""
    status = await spa.get_status_full()
    pump = next(pump for pump in status.pumps if pump.id == pump_id)
    entity_id = f"switch.{spa.brand}_{spa.model}_{entity_suffix}"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    pump.toggle.assert_called()


async def test_pump_turn_off(spa, setup_entry, hass: HomeAssistant) -> None:
    """Test turning off an on pump toggles it."""
    status = await spa.get_status_full()
    pump = next(pump for pump in status.pumps if pump.id == "P2")
    entity_id = f"switch.{spa.brand}_{spa.model}_jet_p2"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    pump.toggle.assert_called()
