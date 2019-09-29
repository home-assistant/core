"""deCONZ device automation tests."""
from asynctest import patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.components.device_automation import (
    _async_get_device_automations as async_get_device_automations,
)

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

DECONZ_SENSOR = {
    "1": {
        "config": {
            "alert": "none",
            "battery": 60,
            "group": "10",
            "on": True,
            "reachable": True,
        },
        "ep": 1,
        "etag": "1b355c0b6d2af28febd7ca9165881952",
        "manufacturername": "IKEA of Sweden",
        "mode": 1,
        "modelid": "TRADFRI on/off switch",
        "name": "TRADFRI on/off switch ",
        "state": {"buttonevent": 2002, "lastupdated": "2019-09-07T07:39:39"},
        "swversion": "1.4.018",
        "type": "ZHASwitch",
        "uniqueid": "d0:cf:5e:ff:fe:71:a4:3a-01-1000",
    }
}

DECONZ_WEB_REQUEST = {"config": DECONZ_CONFIG, "sensors": DECONZ_SENSOR}


def _same_lists(a, b):
    if len(a) != len(b):
        return False

    for d in a:
        if d not in b:
            return False
    return True


async def setup_deconz(hass, options):
    """Create the deCONZ gateway."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=deconz.DOMAIN,
        title="Mock Title",
        data=ENTRY_CONFIG,
        source="test",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        system_options={},
        options=options,
        entry_id="1",
    )

    with patch(
        "pydeconz.DeconzSession.async_get_state", return_value=DECONZ_WEB_REQUEST
    ):
        await deconz.async_setup_entry(hass, config_entry)
    await hass.async_block_till_done()

    hass.config_entries._entries.append(config_entry)

    return hass.data[deconz.DOMAIN][BRIDGEID]


async def test_get_triggers(hass):
    """Test triggers work."""
    gateway = await setup_deconz(hass, options={})
    device_id = gateway.events[0].device_id
    triggers = await async_get_device_automations(hass, "async_get_triggers", device_id)

    expected_triggers = [
        {
            "device_id": device_id,
            "domain": "deconz",
            "platform": "device",
            "type": deconz.device_automation.CONF_SHORT_PRESS,
            "subtype": deconz.device_automation.CONF_TURN_ON,
        },
        {
            "device_id": device_id,
            "domain": "deconz",
            "platform": "device",
            "type": deconz.device_automation.CONF_LONG_PRESS,
            "subtype": deconz.device_automation.CONF_TURN_ON,
        },
        {
            "device_id": device_id,
            "domain": "deconz",
            "platform": "device",
            "type": deconz.device_automation.CONF_LONG_RELEASE,
            "subtype": deconz.device_automation.CONF_TURN_ON,
        },
        {
            "device_id": device_id,
            "domain": "deconz",
            "platform": "device",
            "type": deconz.device_automation.CONF_SHORT_PRESS,
            "subtype": deconz.device_automation.CONF_TURN_OFF,
        },
        {
            "device_id": device_id,
            "domain": "deconz",
            "platform": "device",
            "type": deconz.device_automation.CONF_LONG_PRESS,
            "subtype": deconz.device_automation.CONF_TURN_OFF,
        },
        {
            "device_id": device_id,
            "domain": "deconz",
            "platform": "device",
            "type": deconz.device_automation.CONF_LONG_RELEASE,
            "subtype": deconz.device_automation.CONF_TURN_OFF,
        },
    ]

    assert _same_lists(triggers, expected_triggers)
