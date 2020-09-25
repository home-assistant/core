"""deCONZ switch platform tests."""
from copy import deepcopy

from homeassistant.components import deconz
import homeassistant.components.switch as switch
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.async_mock import patch

SWITCHES = {
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
        "id": "Warning device id",
        "name": "Warning device",
        "type": "Warning device",
        "state": {"alert": "lselect", "reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    },
    "4": {
        "id": "Unsupported switch id",
        "name": "Unsupported switch",
        "type": "Not a smart plug",
        "state": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:03-00",
    },
    "5": {
        "id": "On off relay id",
        "name": "On off relay",
        "state": {"on": True, "reachable": True},
        "type": "On/Off light",
        "uniqueid": "00:00:00:00:00:00:00:04-00",
    },
}


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, switch.DOMAIN, {"switch": {"platform": deconz.DOMAIN}}
        )
        is True
    )
    assert deconz.DOMAIN not in hass.data


async def test_no_switches(hass):
    """Test that no switch entities are created."""
    gateway = await setup_deconz_integration(hass)
    assert len(gateway.deconz_ids) == 0
    assert len(hass.states.async_all()) == 0
    assert len(gateway.entities[switch.DOMAIN]) == 0


async def test_switches(hass):
    """Test that all supported switch entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(SWITCHES)
    gateway = await setup_deconz_integration(hass, get_state_response=data)
    assert "switch.on_off_switch" in gateway.deconz_ids
    assert "switch.smart_plug" in gateway.deconz_ids
    assert "switch.warning_device" in gateway.deconz_ids
    assert "switch.unsupported_switch" not in gateway.deconz_ids
    assert "switch.on_off_relay" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 5
    assert len(gateway.entities[switch.DOMAIN]) == 4

    on_off_switch = hass.states.get("switch.on_off_switch")
    assert on_off_switch.state == "on"

    smart_plug = hass.states.get("switch.smart_plug")
    assert smart_plug.state == "off"

    warning_device = hass.states.get("switch.warning_device")
    assert warning_device.state == "on"

    on_off_relay = hass.states.get("switch.on_off_relay")
    assert on_off_relay.state == "on"

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "1",
        "state": {"on": False},
    }
    gateway.api.event_handler(state_changed_event)
    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "3",
        "state": {"alert": None},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    on_off_switch = hass.states.get("switch.on_off_switch")
    assert on_off_switch.state == "off"

    warning_device = hass.states.get("switch.warning_device")
    assert warning_device.state == "off"

    on_off_switch_device = gateway.api.lights["1"]

    with patch.object(
        on_off_switch_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_ON,
            {"entity_id": "switch.on_off_switch"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"on": True})

    with patch.object(
        on_off_switch_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_OFF,
            {"entity_id": "switch.on_off_switch"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"on": False})

    warning_device_device = gateway.api.lights["3"]

    with patch.object(
        warning_device_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_ON,
            {"entity_id": "switch.warning_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/lights/3/state", json={"alert": "lselect"}
        )

    with patch.object(
        warning_device_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_OFF,
            {"entity_id": "switch.warning_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/lights/3/state", json={"alert": "none"}
        )

    await gateway.async_reset()

    assert len(hass.states.async_all()) == 0
    assert len(gateway.entities[switch.DOMAIN]) == 0
