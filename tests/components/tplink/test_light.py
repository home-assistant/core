"""Tests for light platform."""
from unittest.mock import patch

from pyHS100 import SmartBulb

from homeassistant.components import tplink
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.tplink.common import CONF_DISCOVERY, CONF_LIGHT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_light(hass: HomeAssistant) -> None:
    """Test function."""
    sys_info = {
        "sw_ver": "1.2.3",
        "hw_ver": "2.3.4",
        "mac": "aa:bb:cc:dd:ee:ff",
        "mic_mac": "00:11:22:33:44",
        "type": "light",
        "hwId": "1234",
        "fwId": "4567",
        "oemId": "891011",
        "dev_name": "light1",
        "rssi": 11,
        "latitude": "0",
        "longitude": "0",
        "is_color": True,
        "is_dimmable": True,
        "is_variable_color_temp": True,
        "model": "LB120",
        "alias": "light1",
    }

    light_state = {
        "on_off": SmartBulb.BULB_STATE_ON,
        "dft_on_state": {
            "brightness": 12,
            "color_temp": 3200,
            "hue": 100,
            "saturation": 200,
        },
        "brightness": 13,
        "color_temp": 3300,
        "hue": 110,
        "saturation": 210,
    }

    def set_light_state(state):
        nonlocal light_state
        light_state.update(state)

    set_light_state_patch = patch(
        "homeassistant.components.tplink.common.SmartBulb.set_light_state",
        side_effect=set_light_state,
    )
    get_light_state_patch = patch(
        "homeassistant.components.tplink.common.SmartBulb.get_light_state",
        return_value=light_state,
    )
    current_consumption_patch = patch(
        "homeassistant.components.tplink.common.SmartDevice.current_consumption",
        return_value=3.23,
    )
    get_sysinfo_patch = patch(
        "homeassistant.components.tplink.common.SmartDevice.get_sysinfo",
        return_value=sys_info,
    )
    get_emeter_daily_patch = patch(
        "homeassistant.components.tplink.common.SmartDevice.get_emeter_daily",
        return_value={
            1: 1.01,
            2: 1.02,
            3: 1.03,
            4: 1.04,
            5: 1.05,
            6: 1.06,
            7: 1.07,
            8: 1.08,
            9: 1.09,
            10: 1.10,
            11: 1.11,
            12: 1.12,
        },
    )
    get_emeter_monthly_patch = patch(
        "homeassistant.components.tplink.common.SmartDevice.get_emeter_monthly",
        return_value={
            1: 2.01,
            2: 2.02,
            3: 2.03,
            4: 2.04,
            5: 2.05,
            6: 2.06,
            7: 2.07,
            8: 2.08,
            9: 2.09,
            10: 2.10,
            11: 2.11,
            12: 2.12,
        },
    )

    with set_light_state_patch, get_light_state_patch, current_consumption_patch, get_sysinfo_patch, get_emeter_daily_patch, get_emeter_monthly_patch:
        await async_setup_component(
            hass,
            tplink.DOMAIN,
            {
                tplink.DOMAIN: {
                    CONF_DISCOVERY: False,
                    CONF_LIGHT: [{CONF_HOST: "123.123.123.123"}],
                }
            },
        )
        await hass.async_block_till_done()

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.light1"},
            blocking=True,
        )

        assert hass.states.get("light.light1").state == "off"
        assert light_state["on_off"] == 0

        await hass.async_block_till_done()

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.light1",
                ATTR_COLOR_TEMP: 312,
                ATTR_BRIGHTNESS: 50,
            },
            blocking=True,
        )

        await hass.async_block_till_done()

        state = hass.states.get("light.light1")
        assert state.state == "on"
        assert state.attributes["brightness"] == 48.45
        assert state.attributes["hs_color"] == (110, 210)
        assert state.attributes["color_temp"] == 312
        assert light_state["on_off"] == 1

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.light1",
                ATTR_BRIGHTNESS: 55,
                ATTR_HS_COLOR: (23, 27),
            },
            blocking=True,
        )

        await hass.async_block_till_done()

        state = hass.states.get("light.light1")
        assert state.state == "on"
        assert state.attributes["brightness"] == 53.55
        assert state.attributes["hs_color"] == (23, 27)
        assert state.attributes["color_temp"] == 312
        assert light_state["brightness"] == 21
        assert light_state["hue"] == 23
        assert light_state["saturation"] == 27

        light_state["on_off"] = 0
        light_state["dft_on_state"]["on_off"] = 0
        light_state["brightness"] = 66
        light_state["dft_on_state"]["brightness"] = 66
        light_state["color_temp"] = 6400
        light_state["dft_on_state"]["color_temp"] = 123
        light_state["hue"] = 77
        light_state["dft_on_state"]["hue"] = 77
        light_state["saturation"] = 78
        light_state["dft_on_state"]["saturation"] = 78

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.light1"},
            blocking=True,
        )

        await hass.async_block_till_done()

        state = hass.states.get("light.light1")
        assert state.state == "off"

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.light1"},
            blocking=True,
        )

        await hass.async_block_till_done()

        state = hass.states.get("light.light1")
        assert state.attributes["brightness"] == 168.3
        assert state.attributes["hs_color"] == (77, 78)
        assert state.attributes["color_temp"] == 156
        assert light_state["brightness"] == 66
        assert light_state["hue"] == 77
        assert light_state["saturation"] == 78
