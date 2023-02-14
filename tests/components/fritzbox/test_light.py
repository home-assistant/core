"""Tests for AVM Fritz!Box light component."""
from datetime import timedelta
from unittest.mock import Mock, call

from requests.exceptions import HTTPError

from homeassistant.components.fritzbox.const import (
    COLOR_MODE,
    COLOR_TEMP_MODE,
    DOMAIN as FB_DOMAIN,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_DEVICES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import FritzDeviceLightMock, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(hass: HomeAssistant, fritz: Mock) -> None:
    """Test setup of platform."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    device.color_mode = COLOR_TEMP_MODE
    device.color_temp = 2700

    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake_name"
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 6500


async def test_setup_color(hass: HomeAssistant, fritz: Mock) -> None:
    """Test setup of platform in color mode."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    device.color_mode = COLOR_MODE
    device.hue = 100
    device.saturation = 70 * 255.0 / 100.0

    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake_name"
    assert state.attributes[ATTR_BRIGHTNESS] == 100
    assert state.attributes[ATTR_HS_COLOR] == (100, 70)


async def test_turn_on(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device on."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 100, ATTR_COLOR_TEMP_KELVIN: 3000},
        True,
    )
    assert device.set_state_on.call_count == 1
    assert device.set_level.call_count == 1
    assert device.set_color_temp.call_count == 1
    assert device.set_color_temp.call_args_list == [call(3000)]
    assert device.set_level.call_args_list == [call(100)]


async def test_turn_on_color(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device on in color mode."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 100, ATTR_HS_COLOR: (100, 70)},
        True,
    )
    assert device.set_state_on.call_count == 1
    assert device.set_level.call_count == 1
    assert device.set_unmapped_color.call_count == 1
    assert device.set_level.call_args_list == [call(100)]
    assert device.set_unmapped_color.call_args_list == [
        call((100, round(70 * 255.0 / 100.0)))
    ]


async def test_turn_on_color_unsupported_api_method(
    hass: HomeAssistant, fritz: Mock
) -> None:
    """Test turn device on in mapped color mode if unmapped is not supported."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    mockresponse = Mock()
    mockresponse.status_code = 400

    error = HTTPError("Bad Request")
    error.response = mockresponse
    device.set_unmapped_color.side_effect = error

    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 100, ATTR_HS_COLOR: (100, 70)},
        True,
    )
    assert device.set_state_on.call_count == 1
    assert device.set_level.call_count == 1
    assert device.set_color.call_count == 1
    assert device.set_level.call_args_list == [call(100)]
    assert device.set_color.call_args_list == [call((100, 70))]


async def test_turn_off(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device off."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_state_off.call_count == 1


async def test_update(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update without error."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert fritz().update_devices.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 1


async def test_update_error(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update with error."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    fritz().update_devices.side_effect = HTTPError("Boom")
    assert not await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 2

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert fritz().update_devices.call_count == 4
    assert fritz().login.call_count == 4
