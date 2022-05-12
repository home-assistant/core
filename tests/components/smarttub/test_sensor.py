"""Test the SmartTub sensor platform."""

import pytest
import smarttub


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


async def test_primary_filtration(spa, spa_state, setup_entry, hass):
    """Test the primary filtration cycle sensor."""

    entity_id = f"sensor.{spa.brand}_{spa.model}_primary_filtration_cycle"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "inactive"
    assert state.attributes["duration"] == 4
    assert state.attributes["cycle_last_updated"] is not None
    assert state.attributes["mode"] == "normal"
    assert state.attributes["start_hour"] == 2

    await hass.services.async_call(
        "smarttub",
        "set_primary_filtration",
        {"entity_id": entity_id, "duration": 8, "start_hour": 1},
        blocking=True,
    )
    spa_state.primary_filtration.set.assert_called_with(duration=8, start_hour=1)


async def test_secondary_filtration(spa, spa_state, setup_entry, hass):
    """Test the secondary filtration cycle sensor."""

    entity_id = f"sensor.{spa.brand}_{spa.model}_secondary_filtration_cycle"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "inactive"
    assert state.attributes["cycle_last_updated"] is not None
    assert state.attributes["mode"] == "away"

    await hass.services.async_call(
        "smarttub",
        "set_secondary_filtration",
        {
            "entity_id": entity_id,
            "mode": "frequent",
        },
        blocking=True,
    )
    spa_state.secondary_filtration.set_mode.assert_called_with(
        mode=smarttub.SpaSecondaryFiltrationCycle.SecondaryFiltrationMode.FREQUENT
    )
