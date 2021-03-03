"""Test the SmartTub sensor platform."""

import pytest


@pytest.mark.parametrize(
    "entity_suffix,expected_state",
    [
        ("state", "normal"),
        ("flow_switch", "open"),
        ("ozone", "off"),
        ("uv", "off"),
        ("blowout_cycle", "inactive"),
        ("cleanup_cycle", "inactive"),
    ],
)
async def test_sensor(spa, setup_entry, hass, entity_suffix, expected_state):
    """Test simple sensors."""

    entity_id = f"sensor.{spa.brand}_{spa.model}_{entity_suffix}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


async def test_primary_filtration(spa, setup_entry, hass):
    """Test the primary filtration cycle sensor."""

    entity_id = f"sensor.{spa.brand}_{spa.model}_primary_filtration_cycle"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "inactive"
    assert state.attributes["duration"] == 4
    assert state.attributes["cycle_last_updated"] is not None
    assert state.attributes["mode"] == "normal"
    assert state.attributes["start_hour"] == 2


async def test_secondary_filtration(spa, setup_entry, hass):
    """Test the secondary filtration cycle sensor."""

    entity_id = f"sensor.{spa.brand}_{spa.model}_secondary_filtration_cycle"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "inactive"
    assert state.attributes["cycle_last_updated"] is not None
    assert state.attributes["mode"] == "away"
