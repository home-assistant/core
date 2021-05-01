"""Tests for light platform."""
from datetime import timedelta
import logging
from typing import Callable, NamedTuple
from unittest.mock import Mock, PropertyMock, patch

from pyHS100 import SmartDeviceException
import pytest

from homeassistant.components import tplink
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.tplink.common import (
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_LIGHT,
)
from homeassistant.components.tplink.light import SLEEP_TIME
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


class LightMockData(NamedTuple):
    """Mock light data."""

    sys_info: dict
    light_state: dict
    set_light_state: Callable[[dict], None]
    set_light_state_mock: Mock
    get_light_state_mock: Mock
    current_consumption_mock: Mock
    get_sysinfo_mock: Mock
    get_emeter_daily_mock: Mock
    get_emeter_monthly_mock: Mock


class SmartSwitchMockData(NamedTuple):
    """Mock smart switch data."""

    sys_info: dict
    state_mock: Mock
    brightness_mock: Mock
    get_sysinfo_mock: Mock


@pytest.fixture(name="unknown_light_mock_data")
def unknown_light_mock_data_fixture() -> None:
    """Create light mock data."""
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
        "model": "Foo",
        "alias": "light1",
    }
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

    def set_light_state(state) -> None:
        nonlocal light_state
        drt_on_state = light_state["dft_on_state"]
        drt_on_state.update(state.get("dft_on_state", {}))

        light_state.update(state)
        light_state["dft_on_state"] = drt_on_state
        return light_state

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

    with set_light_state_patch as set_light_state_mock, get_light_state_patch as get_light_state_mock, current_consumption_patch as current_consumption_mock, get_sysinfo_patch as get_sysinfo_mock, get_emeter_daily_patch as get_emeter_daily_mock, get_emeter_monthly_patch as get_emeter_monthly_mock:
        yield LightMockData(
            sys_info=sys_info,
            light_state=light_state,
            set_light_state=set_light_state,
            set_light_state_mock=set_light_state_mock,
            get_light_state_mock=get_light_state_mock,
            current_consumption_mock=current_consumption_mock,
            get_sysinfo_mock=get_sysinfo_mock,
            get_emeter_daily_mock=get_emeter_daily_mock,
            get_emeter_monthly_mock=get_emeter_monthly_mock,
        )


@pytest.fixture(name="light_mock_data")
def light_mock_data_fixture() -> None:
    """Create light mock data."""
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

    def set_light_state(state) -> None:
        nonlocal light_state
        drt_on_state = light_state["dft_on_state"]
        drt_on_state.update(state.get("dft_on_state", {}))

        light_state.update(state)
        light_state["dft_on_state"] = drt_on_state
        return light_state

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

    with set_light_state_patch as set_light_state_mock, get_light_state_patch as get_light_state_mock, current_consumption_patch as current_consumption_mock, get_sysinfo_patch as get_sysinfo_mock, get_emeter_daily_patch as get_emeter_daily_mock, get_emeter_monthly_patch as get_emeter_monthly_mock:
        yield LightMockData(
            sys_info=sys_info,
            light_state=light_state,
            set_light_state=set_light_state,
            set_light_state_mock=set_light_state_mock,
            get_light_state_mock=get_light_state_mock,
            current_consumption_mock=current_consumption_mock,
            get_sysinfo_mock=get_sysinfo_mock,
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
        "type": "switch",
        "hwId": "1234",
        "fwId": "4567",
        "oemId": "891011",
        "dev_name": "dimmer1",
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

    def state(*args, **kwargs):
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

    get_sysinfo_patch = patch(
        "homeassistant.components.tplink.common.SmartDevice.get_sysinfo",
        return_value=sys_info,
    )
    state_patch = patch(
        "homeassistant.components.tplink.common.SmartPlug.state",
        new_callable=PropertyMock,
        side_effect=state,
    )
    brightness_patch = patch(
        "homeassistant.components.tplink.common.SmartPlug.brightness",
        new_callable=PropertyMock,
        side_effect=brightness,
    )
    with brightness_patch as brightness_mock, state_patch as state_mock, get_sysinfo_patch as get_sysinfo_mock:
        yield SmartSwitchMockData(
            sys_info=sys_info,
            brightness_mock=brightness_mock,
            state_mock=state_mock,
            get_sysinfo_mock=get_sysinfo_mock,
        )


async def update_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Run an update action for an entity."""
    await hass.services.async_call(
        HA_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def test_smartswitch(
    hass: HomeAssistant, dimmer_switch_mock_data: SmartSwitchMockData
) -> None:
    """Test function."""
    sys_info = dimmer_switch_mock_data.sys_info

    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        tplink.DOMAIN,
        {
            tplink.DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_DIMMER: [{CONF_HOST: "123.123.123.123"}],
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.dimmer1")

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "light.dimmer1"}, blocking=True
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.dimmer1")

    assert hass.states.get("light.dimmer1").state == "off"
    assert sys_info["relay_state"] == 0

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.dimmer1", ATTR_BRIGHTNESS: 50},
        blocking=True,
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.dimmer1")

    state = hass.states.get("light.dimmer1")
    assert state.state == "on"
    assert state.attributes["brightness"] == 51
    assert sys_info["relay_state"] == 1

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.dimmer1", ATTR_BRIGHTNESS: 55},
        blocking=True,
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.dimmer1")

    state = hass.states.get("light.dimmer1")
    assert state.state == "on"
    assert state.attributes["brightness"] == 56
    assert sys_info["brightness"] == 22

    sys_info["relay_state"] = 0
    sys_info["brightness"] = 66

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "light.dimmer1"}, blocking=True
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.dimmer1")

    state = hass.states.get("light.dimmer1")
    assert state.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "light.dimmer1"}, blocking=True
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.dimmer1")

    state = hass.states.get("light.dimmer1")
    assert state.state == "on"
    assert state.attributes["brightness"] == 168
    assert sys_info["brightness"] == 66


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


async def test_light(hass: HomeAssistant, light_mock_data: LightMockData) -> None:
    """Test function."""
    light_state = light_mock_data.light_state
    set_light_state = light_mock_data.set_light_state

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

    assert hass.states.get("light.light1")

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "light.light1"}, blocking=True
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.light1")

    assert hass.states.get("light.light1").state == "off"
    assert light_state["on_off"] == 0

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.light1", ATTR_COLOR_TEMP: 222, ATTR_BRIGHTNESS: 50},
        blocking=True,
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.light1")

    state = hass.states.get("light.light1")
    assert state.state == "on"
    assert state.attributes["brightness"] == 51
    assert state.attributes["color_temp"] == 222
    assert "hs_color" not in state.attributes
    assert light_state["on_off"] == 1

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.light1", ATTR_BRIGHTNESS: 55, ATTR_HS_COLOR: (23, 27)},
        blocking=True,
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.light1")

    state = hass.states.get("light.light1")
    assert state.state == "on"
    assert state.attributes["brightness"] == 56
    assert state.attributes["hs_color"] == (23, 27)
    assert "color_temp" not in state.attributes
    assert light_state["brightness"] == 22
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
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "light.light1"}, blocking=True
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.light1")

    state = hass.states.get("light.light1")
    assert state.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "light.light1"}, blocking=True
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.light1")

    state = hass.states.get("light.light1")
    assert state.state == "on"
    assert state.attributes["brightness"] == 168
    assert state.attributes["color_temp"] == 156
    assert "hs_color" not in state.attributes
    assert light_state["brightness"] == 66
    assert light_state["hue"] == 77
    assert light_state["saturation"] == 78

    set_light_state({"brightness": 91, "dft_on_state": {"brightness": 91}})
    await update_entity(hass, "light.light1")

    state = hass.states.get("light.light1")
    assert state.attributes["brightness"] == 232


async def test_get_light_state_retry(
    hass: HomeAssistant, light_mock_data: LightMockData
) -> None:
    """Test function."""
    # Setup test for retries for sysinfo.
    get_sysinfo_call_count = 0

    def get_sysinfo_side_effect():
        nonlocal get_sysinfo_call_count
        get_sysinfo_call_count += 1

        # Need to fail on the 2nd call because the first call is used to
        # determine if the device is online during the light platform's
        # setup hook.
        if get_sysinfo_call_count == 2:
            raise SmartDeviceException()

        return light_mock_data.sys_info

    light_mock_data.get_sysinfo_mock.side_effect = get_sysinfo_side_effect

    # Setup test for retries of setting state information.
    set_state_call_count = 0

    def set_light_state_side_effect(state_data: dict):
        nonlocal set_state_call_count, light_mock_data
        set_state_call_count += 1

        if set_state_call_count == 1:
            raise SmartDeviceException()

        return light_mock_data.set_light_state(state_data)

    light_mock_data.set_light_state_mock.side_effect = set_light_state_side_effect

    # Setup component.
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

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "light.light1"}, blocking=True
    )
    await hass.async_block_till_done()
    await update_entity(hass, "light.light1")

    assert light_mock_data.get_sysinfo_mock.call_count > 1
    assert light_mock_data.get_light_state_mock.call_count > 1
    assert light_mock_data.set_light_state_mock.call_count > 1

    assert light_mock_data.get_sysinfo_mock.call_count < 40
    assert light_mock_data.get_light_state_mock.call_count < 40
    assert light_mock_data.set_light_state_mock.call_count < 10


async def test_update_failure(
    hass: HomeAssistant, light_mock_data: LightMockData, caplog
):
    """Test that update failures are logged."""

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
    caplog.clear()
    caplog.set_level(logging.WARNING)
    await hass.helpers.entity_component.async_update_entity("light.light1")
    assert caplog.text == ""

    with patch("homeassistant.components.tplink.light.MAX_ATTEMPTS", 0):
        caplog.clear()
        caplog.set_level(logging.WARNING)
        await hass.helpers.entity_component.async_update_entity("light.light1")
        assert "Could not read state for 123.123.123.123|light1" in caplog.text

    get_state_call_count = 0

    def get_light_state_side_effect():
        nonlocal get_state_call_count
        get_state_call_count += 1

        if get_state_call_count == 1:
            raise SmartDeviceException()

        return light_mock_data.light_state

    light_mock_data.get_light_state_mock.side_effect = get_light_state_side_effect

    with patch("homeassistant.components.tplink.light", MAX_ATTEMPTS=2, SLEEP_TIME=0):
        caplog.clear()
        caplog.set_level(logging.DEBUG)

        await update_entity(hass, "light.light1")
        assert (
            f"Retrying in {SLEEP_TIME} seconds for 123.123.123.123|light1"
            in caplog.text
        )
        assert "Device 123.123.123.123|light1 responded after " in caplog.text


async def test_async_setup_entry_unavailable(
    hass: HomeAssistant, light_mock_data: LightMockData, caplog
):
    """Test unavailable devices trigger a later retry."""
    caplog.clear()
    caplog.set_level(logging.WARNING)

    with patch(
        "homeassistant.components.tplink.common.SmartDevice.get_sysinfo",
        side_effect=SmartDeviceException,
    ):
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
        assert not hass.states.get("light.light1")

    future = utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert hass.states.get("light.light1")
