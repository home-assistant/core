"""Tests for light platform."""
from datetime import timedelta
import logging
from typing import Callable, NamedTuple
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from kasa import SmartDeviceException
import pytest

from homeassistant.components import tplink
from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
from homeassistant.components.tplink.const import CONF_DISCOVERY, CONF_LIGHT
from homeassistant.const import CONF_HOST, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

MOCK_ENERGY_DATA = {
    "smartlife.iot.common.emeter": {
        "get_daystat": {
            "day_list": [
                {"day": 23, "energy_wh": 2, "month": 9, "year": 2021},
                {"day": 24, "energy_wh": 66, "month": 9, "year": 2021},
            ],
            "err_code": 0,
        },
        "get_monthstat": {
            "err_code": 0,
            "month_list": [{"energy_wh": 68, "month": 9, "year": 2021}],
        },
        "get_realtime": {"err_code": 0, "power_mw": 10800},
    }
}


class LightMockData(NamedTuple):
    """Mock light data."""

    query_mock: AsyncMock
    sys_info: dict
    light_state: dict
    set_light_state: Callable[[dict], None]
    set_light_state_mock: Mock
    get_light_state_mock: Mock
    current_consumption_mock: Mock
    sys_info_mock: Mock
    get_emeter_daily_mock: Mock
    get_emeter_monthly_mock: Mock


class SmartSwitchMockData(NamedTuple):
    """Mock smart switch data."""

    query_mock: AsyncMock
    sys_info: dict
    is_on_mock: Mock
    brightness_mock: Mock
    sys_info_mock: Mock


@pytest.fixture(name="unknown_light_mock_data")
def unknown_light_mock_data_fixture() -> None:
    """Create light mock data."""
    light_state = {
        "on_off": True,
        "dft_on_state": {
            "brightness": 12,
            "color_temp": 3200,
            "hue": 110,
            "saturation": 90,
        },
        "brightness": 13,
        "color_temp": 3300,
        "hue": 110,
        "saturation": 90,
    }
    sys_info = {
        "sw_ver": "1.2.3",
        "type": "smartbulb",
        "hw_ver": "2.3.4",
        "mac": "aa:bb:cc:dd:ee:ff",
        "mic_mac": "00:11:22:33:44",
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
        "model": "Foo",
        "alias": "light1",
        "light_state": light_state,
    }

    def set_light_state(state) -> None:
        nonlocal light_state
        drt_on_state = light_state["dft_on_state"]
        drt_on_state.update(state.get("dft_on_state", {}))

        light_state.update(state)
        light_state["dft_on_state"] = drt_on_state
        return light_state

    set_light_state_patch = patch(
        "kasa.smartbulb.SmartBulb.set_light_state",
        side_effect=set_light_state,
    )
    get_light_state_patch = patch(
        "kasa.smartbulb.SmartBulb.get_light_state",
        return_value=light_state,
    )
    current_consumption_patch = patch(
        "kasa.smartdevice.SmartDevice.current_consumption",
        return_value=3.23,
    )
    sys_info_patch = patch(
        "kasa.smartdevice.SmartDevice.sys_info",
        sys_info,
    )
    get_emeter_daily_patch = patch(
        "kasa.smartdevice.SmartDevice.get_emeter_daily",
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
        "kasa.smartdevice.SmartDevice.get_emeter_monthly",
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
    query_patch = patch(
        "kasa.smartdevice.TPLinkSmartHomeProtocol.query",
        return_value={"system": {"get_sysinfo": sys_info}, **MOCK_ENERGY_DATA},
    )
    with query_patch as query_mock, set_light_state_patch as set_light_state_mock, get_light_state_patch as get_light_state_mock, current_consumption_patch as current_consumption_mock, sys_info_patch as sys_info_mock, get_emeter_daily_patch as get_emeter_daily_mock, get_emeter_monthly_patch as get_emeter_monthly_mock:
        yield LightMockData(
            query_mock=query_mock,
            sys_info=sys_info,
            light_state=light_state,
            set_light_state=set_light_state,
            set_light_state_mock=set_light_state_mock,
            get_light_state_mock=get_light_state_mock,
            current_consumption_mock=current_consumption_mock,
            sys_info_mock=sys_info_mock,
            get_emeter_daily_mock=get_emeter_daily_mock,
            get_emeter_monthly_mock=get_emeter_monthly_mock,
        )


@pytest.fixture(name="light_mock_data")
def light_mock_data_fixture() -> None:
    """Create light mock data."""
    light_state = {
        "on_off": True,
        "dft_on_state": {
            "brightness": 12,
            "color_temp": 3200,
            "hue": 110,
            "saturation": 90,
        },
        "brightness": 13,
        "color_temp": 3300,
        "hue": 110,
        "saturation": 90,
    }
    sys_info = {
        "sw_ver": "1.2.3",
        "hw_ver": "2.3.4",
        "mac": "aa:bb:cc:dd:ee:ff",
        "mic_mac": "00:11:22:33:44",
        "type": "smartbulb",
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
        "light_state": light_state,
    }

    def set_light_state(state) -> None:
        nonlocal light_state
        drt_on_state = light_state["dft_on_state"]
        drt_on_state.update(state.get("dft_on_state", {}))

        light_state.update(state)
        light_state["dft_on_state"] = drt_on_state
        return light_state

    set_light_state_patch = patch(
        "kasa.smartbulb.SmartBulb.set_light_state",
        side_effect=set_light_state,
    )
    get_light_state_patch = patch(
        "kasa.smartbulb.SmartBulb.get_light_state",
        return_value=light_state,
    )
    current_consumption_patch = patch(
        "kasa.smartdevice.SmartDevice.current_consumption",
        return_value=3.23,
    )
    sys_info_patch = patch(
        "kasa.smartdevice.SmartDevice.sys_info",
        sys_info,
    )
    get_emeter_daily_patch = patch(
        "kasa.smartdevice.SmartDevice.get_emeter_daily",
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
        "kasa.smartdevice.SmartDevice.get_emeter_monthly",
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
    query_patch = patch(
        "kasa.smartdevice.TPLinkSmartHomeProtocol.query",
        return_value={"system": {"get_sysinfo": sys_info}, **MOCK_ENERGY_DATA},
    )
    with query_patch as query_mock, set_light_state_patch as set_light_state_mock, get_light_state_patch as get_light_state_mock, current_consumption_patch as current_consumption_mock, sys_info_patch as sys_info_mock, get_emeter_daily_patch as get_emeter_daily_mock, get_emeter_monthly_patch as get_emeter_monthly_mock:
        yield LightMockData(
            query_mock=query_mock,
            sys_info=sys_info,
            light_state=light_state,
            set_light_state=set_light_state,
            set_light_state_mock=set_light_state_mock,
            get_light_state_mock=get_light_state_mock,
            current_consumption_mock=current_consumption_mock,
            sys_info_mock=sys_info_mock,
            get_emeter_daily_mock=get_emeter_daily_mock,
            get_emeter_monthly_mock=get_emeter_monthly_mock,
        )


@pytest.fixture(name="dimmer_switch_mock_data")
def dimmer_switch_mock_data_fixture() -> None:
    """Create dimmer switch mock data."""
    sys_info = {
        "sw_ver": "1.2.3",
        "hw_ver": "2.3.4",
        "mac": "aa:bb:cc:dd:ee:ff",
        "mic_mac": "00:11:22:33:44",
        "type": "smartplug",
        "hwId": "1234",
        "fwId": "4567",
        "oemId": "891011",
        "dev_name": "dimmer1",
        "led_off": 1,
        "rssi": 11,
        "latitude": "0",
        "longitude": "0",
        "is_color": False,
        "is_dimmable": True,
        "is_variable_color_temp": False,
        "model": "HS220",
        "alias": "dimmer1",
        "feature": ":",
        "relay_state": 1,
        "brightness": 13,
    }

    def is_on(*args, **kwargs):
        nonlocal sys_info
        if len(args) == 0:
            return sys_info["relay_state"]
        if args[0] == "ON":
            sys_info["relay_state"] = 1
        else:
            sys_info["relay_state"] = 0

    def brightness(*args, **kwargs):
        nonlocal sys_info
        if len(args) == 0:
            return sys_info["brightness"]
        if sys_info["brightness"] == 0:
            sys_info["relay_state"] = 0
        else:
            sys_info["relay_state"] = 1
            sys_info["brightness"] = args[0]

    sys_info_patch = patch(
        "kasa.smartdevice.SmartDevice.sys_info",
        sys_info,
    )
    is_on_patch = patch(
        "kasa.smartdimmer.SmartDimmer.is_on",
        new_callable=PropertyMock,
        side_effect=is_on,
    )
    brightness_patch = patch(
        "kasa.smartdimmer.SmartDimmer.brightness",
        new_callable=PropertyMock,
        side_effect=brightness,
    )
    query_patch = patch(
        "kasa.smartdevice.TPLinkSmartHomeProtocol.query",
        return_value={"system": {"get_sysinfo": sys_info}, **MOCK_ENERGY_DATA},
    )
    with query_patch as query_mock, brightness_patch as brightness_mock, is_on_patch as is_on_mock, sys_info_patch as sys_info_mock:
        yield SmartSwitchMockData(
            query=query_mock,
            sys_info=sys_info,
            brightness_mock=brightness_mock,
            is_on_mock=is_on_mock,
            sys_info_mock=sys_info_mock,
        )


async def update_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Run an update action for an entity."""
    future = utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()


async def test_unknown_light(
    hass: HomeAssistant, unknown_light_mock_data: LightMockData
) -> None:
    """Test function."""
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()

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

    state = hass.states.get("light.light1")
    assert state.state == "on"
    assert state.attributes["min_mireds"] == 200
    assert state.attributes["max_mireds"] == 370


async def test_update_failure(
    hass: HomeAssistant, light_mock_data: LightMockData, caplog
):
    """Test that update failures are logged."""

    await hass.async_block_till_done()

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
    assert hass.states.get("light.light1").state == STATE_ON

    caplog.clear()
    caplog.set_level(logging.WARNING)
    await update_entity(hass, "light.light1")
    assert caplog.text == ""
    assert hass.states.get("light.light1").state == STATE_ON

    light_mock_data.query_mock.side_effect = SmartDeviceException
    caplog.clear()
    caplog.set_level(logging.WARNING)
    await update_entity(hass, "light.light1")
    assert hass.states.get("light.light1").state == STATE_UNAVAILABLE
