"""deCONZ switch platform tests."""

from copy import deepcopy
from unittest.mock import patch

from homeassistant.components.deconz import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

POWER_PLUGS = {
    "1": {
        "id": "On off switch id",
        "name": "On off switch",
        "type": "On/Off plug-in unit",
        "state": {"on": True, "reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    },
    "2": {
        "id": "Smart plug id",
        "name": "Smart plug",
        "type": "Smart plug",
        "state": {"on": False, "reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
    "3": {
        "id": "Unsupported switch id",
        "name": "Unsupported switch",
        "type": "Not a switch",
        "state": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:03-00",
    },
    "4": {
        "id": "On off relay id",
        "name": "On off relay",
        "state": {"on": True, "reachable": True},
        "type": "On/Off light",
        "uniqueid": "00:00:00:00:00:00:00:04-00",
    },
}

SIRENS = {
    "1": {
        "id": "Warning device id",
        "name": "Warning device",
        "type": "Warning device",
        "state": {"alert": "lselect", "reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    },
    "2": {
        "id": "Unsupported switch id",
        "name": "Unsupported switch",
        "type": "Not a switch",
        "state": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
}


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, SWITCH_DOMAIN, {"switch": {"platform": DECONZ_DOMAIN}}
        )
        is True
    )
    assert DECONZ_DOMAIN not in hass.data


async def test_no_switches(hass):
    """Test that no switch entities are created."""
    await setup_deconz_integration(hass)
    assert len(hass.states.async_all()) == 0


async def test_power_plugs(hass):
    """Test that all supported switch entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(POWER_PLUGS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 4
    assert hass.states.get("switch.on_off_switch").state == STATE_ON
    assert hass.states.get("switch.smart_plug").state == STATE_OFF
    assert hass.states.get("switch.on_off_relay").state == STATE_ON
    assert hass.states.get("switch.unsupported_switch") is None

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "1",
        "state": {"on": False},
    }
    gateway.api.event_handler(state_changed_event)

    assert hass.states.get("switch.on_off_switch").state == STATE_OFF

    # Verify service calls

    on_off_switch_device = gateway.api.lights["1"]

    # Service turn on power plug

    with patch.object(
        on_off_switch_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.on_off_switch"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"on": True})

    # Service turn off power plug

    with patch.object(
        on_off_switch_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.on_off_switch"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"on": False})

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(hass.states.async_all()) == 4
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_sirens(hass):
    """Test that siren entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(SIRENS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("switch.warning_device").state == STATE_ON
    assert hass.states.get("switch.unsupported_switch") is None

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "1",
        "state": {"alert": None},
    }
    gateway.api.event_handler(state_changed_event)

    assert hass.states.get("switch.warning_device").state == STATE_OFF

    # Verify service calls

    warning_device_device = gateway.api.lights["1"]

    # Service turn on siren

    with patch.object(
        warning_device_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.warning_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/lights/1/state", json={"alert": "lselect"}
        )

    # Service turn off siren

    with patch.object(
        warning_device_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.warning_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/lights/1/state", json={"alert": "none"}
        )

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(hass.states.async_all()) == 2
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
