"""Tests for light platform."""
from typing import Any, Dict, Optional
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

    emeter = {
        "voltage_mv": 12,
        "power_mw": 13,
        "current_ma": 14,
        "energy_wh": 15,
        "total_wh": 16,
        "voltage": 17,
        "power": 18,
        "current": 19,
        "total": 20,
        "energy": 21,
    }

    def query_helper(target: str, cmd: str, arg: Optional[Dict] = None) -> Any:
        nonlocal sys_info, light_state, emeter
        print("query_helper", target, cmd)

        if target == "system" and cmd == "get_sysinfo":
            return sys_info

        if (
            target == "smartlife.iot.smartbulb.lightingservice"
            and cmd == "get_light_state"
        ):
            return light_state

        if (
            target == "smartlife.iot.smartbulb.lightingservice"
            and cmd == "transition_light_state"
        ):
            light_state["dft_on_state"] = {
                **light_state["dft_on_state"],
                **arg,
            }
            light_state = {**light_state, **arg}
            return {}

        if target == "smartlife.iot.common.emeter" and cmd == "get_realtime":
            return emeter

        if target == "smartlife.iot.common.emeter" and cmd == "get_daystat":
            return {
                "day_list": [{**emeter, **{"day": "2"}}],
            }

        if target == "smartlife.iot.common.emeter" and cmd == "get_monthstat":
            return {
                "month_list": [{**emeter, **{"month": "3"}}],
            }

        return {}

    query_helper_patch = patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper",
        side_effect=query_helper,
    )

    with query_helper_patch:
        await async_setup_component(
            hass,
            tplink.DOMAIN,
            {
                tplink.DOMAIN: {
                    CONF_DISCOVERY: False,
                    CONF_LIGHT: [{CONF_HOST: "123.123.123.123"}],
                    # CONF_SWITCH: [{CONF_HOST: "321.321.321.321"}],
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
        assert light_state["dft_on_state"]["on_off"] == 0

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
        assert light_state["dft_on_state"]["on_off"] == 1
        assert light_state["color_temp"] == 3205
        assert light_state["dft_on_state"]["color_temp"] == 3205
        assert light_state["brightness"] == 19
        assert light_state["dft_on_state"]["brightness"] == 19

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
