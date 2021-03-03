"""deCONZ switch platform tests."""

from copy import deepcopy

from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)

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


async def test_no_switches(hass, aioclient_mock):
    """Test that no switch entities are created."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_power_plugs(hass, aioclient_mock):
    """Test that all supported switch entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(POWER_PLUGS)
    config_entry = await setup_deconz_integration(
        hass, aioclient_mock, get_state_response=data
    )
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

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/1/state")

    # Service turn on power plug

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.on_off_switch"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True}

    # Service turn off power plug

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.on_off_switch"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"on": False}

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(hass.states.async_all()) == 4
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_sirens(hass, aioclient_mock):
    """Test that siren entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(SIRENS)
    config_entry = await setup_deconz_integration(
        hass, aioclient_mock, get_state_response=data
    )
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

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/1/state")

    # Service turn on siren

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.warning_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"alert": "lselect"}

    # Service turn off siren

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.warning_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"alert": "none"}

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(hass.states.async_all()) == 2
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
