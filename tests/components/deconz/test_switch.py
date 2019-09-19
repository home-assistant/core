"""deCONZ switch platform tests."""
from copy import deepcopy

from asynctest import patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.setup import async_setup_component


import homeassistant.components.switch as switch

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
}

BRIDGEID = "0123456789"

ENTRY_CONFIG = {
    deconz.config_flow.CONF_API_KEY: "ABCDEF",
    deconz.config_flow.CONF_BRIDGEID: BRIDGEID,
    deconz.config_flow.CONF_HOST: "1.2.3.4",
    deconz.config_flow.CONF_PORT: 80,
}

DECONZ_CONFIG = {
    "bridgeid": BRIDGEID,
    "mac": "00:11:22:33:44:55",
    "name": "deCONZ mock gateway",
    "sw_version": "2.05.69",
    "websocketport": 1234,
}

DECONZ_WEB_REQUEST = {"config": DECONZ_CONFIG}


async def setup_deconz_integration(hass, config, options, get_state_response):
    """Create the deCONZ gateway."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=deconz.DOMAIN,
        title="Mock Title",
        data=config,
        source="test",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        system_options={},
        options=options,
        entry_id="1",
    )

    with patch(
        "pydeconz.DeconzSession.async_get_state", return_value=get_state_response
    ), patch("pydeconz.DeconzSession.start", return_value=True):
        await deconz.async_setup_entry(hass, config_entry)
    await hass.async_block_till_done()

    hass.config_entries._entries.append(config_entry)

    return hass.data[deconz.DOMAIN][config[deconz.CONF_BRIDGEID]]


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
    data = deepcopy(DECONZ_WEB_REQUEST)
    gateway = await setup_deconz_integration(
        hass, ENTRY_CONFIG, options={}, get_state_response=data
    )
    assert len(gateway.deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_switches(hass):
    """Test that all supported switch entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(SWITCHES)
    gateway = await setup_deconz_integration(
        hass, ENTRY_CONFIG, options={}, get_state_response=data
    )
    assert "switch.on_off_switch" in gateway.deconz_ids
    assert "switch.smart_plug" in gateway.deconz_ids
    assert "switch.warning_device" in gateway.deconz_ids
    assert "switch.unsupported_switch" not in gateway.deconz_ids
    assert len(hass.states.async_all()) == 6

    on_off_switch = hass.states.get("switch.on_off_switch")
    assert on_off_switch.state == "on"

    smart_plug = hass.states.get("switch.smart_plug")
    assert smart_plug.state == "off"

    warning_device = hass.states.get("switch.warning_device")
    assert warning_device.state == "on"

    on_off_switch_device = gateway.api.lights["1"]
    warning_device_device = gateway.api.lights["3"]

    on_off_switch_device.async_update({"state": {"on": False}})
    warning_device_device.async_update({"state": {"alert": None}})
    await hass.async_block_till_done()

    on_off_switch = hass.states.get("switch.on_off_switch")
    assert on_off_switch.state == "off"

    warning_device = hass.states.get("switch.warning_device")
    assert warning_device.state == "off"

    with patch.object(
        on_off_switch_device, "_async_set_callback", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_ON,
            {"entity_id": "switch.on_off_switch"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("/lights/1/state", {"on": True})

    with patch.object(
        on_off_switch_device, "_async_set_callback", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_OFF,
            {"entity_id": "switch.on_off_switch"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("/lights/1/state", {"on": False})

    with patch.object(
        warning_device_device, "_async_set_callback", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_ON,
            {"entity_id": "switch.warning_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("/lights/3/state", {"alert": "lselect"})

    with patch.object(
        warning_device_device, "_async_set_callback", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_OFF,
            {"entity_id": "switch.warning_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("/lights/3/state", {"alert": "none"})
