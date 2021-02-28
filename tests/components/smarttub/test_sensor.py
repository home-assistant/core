"""Test the SmartTub sensor platform."""

import smarttub

from homeassistant.helpers.service import async_prepare_call_from_config

from . import trigger_update


async def test_simple_sensors(spa, setup_entry, hass):
    """Test simple sensors."""

    entity_id = f"sensor.{spa.brand}_{spa.model}_state"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "normal"

    spa.get_status.return_value.state = "BAD"
    await trigger_update(hass)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "bad"

    entity_id = f"sensor.{spa.brand}_{spa.model}_flow_switch"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "open"

    entity_id = f"sensor.{spa.brand}_{spa.model}_ozone"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    entity_id = f"sensor.{spa.brand}_{spa.model}_uv"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    entity_id = f"sensor.{spa.brand}_{spa.model}_blowout_cycle"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "inactive"

    entity_id = f"sensor.{spa.brand}_{spa.model}_cleanup_cycle"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "inactive"


async def test_filtration_cycles(spa, setup_entry, hass):
    """Test filtration cycles, which also have services."""

    entity_id = f"sensor.{spa.brand}_{spa.model}_primary_filtration_cycle"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "inactive"
    assert state.attributes["duration"] == 4
    assert state.attributes["last_updated"] is not None
    assert state.attributes["mode"] == "normal"
    assert state.attributes["start_hour"] == 2

    call = async_prepare_call_from_config(hass, {
        "service": "smarttub.set_primary_filtration",
        "target": {},
    })

    await hass.services.async_call(
        "smarttub",
        "set_primary_filtration",
        {"entity_id": entity_id, "duration": 8, "start_hour": 1},
        blocking=True,
    )
    spa.get_status.return_value.primary_filtration.set.assert_called_with(
        duration=8, start_hour=1
    )

    entity_id = f"sensor.{spa.brand}_{spa.model}_secondary_filtration_cycle"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "inactive"
    assert state.attributes["last_updated"] is not None
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
    spa.get_status.return_value.secondary_filtration.set_mode.assert_called_with(
        mode=smarttub.SpaSecondaryFiltrationCycle.SecondaryFiltrationMode.FREQUENT
    )
