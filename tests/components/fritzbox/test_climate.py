"""Tests for AVM Fritz!Box climate component."""
from datetime import timedelta

from asynctest.mock import Mock, patch
import pytest
from requests.exceptions import HTTPError

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_COMFORT,
    PRESET_ECO,
)
from homeassistant.components.fritzbox.const import (
    ATTR_STATE_BATTERY_LOW,
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_HOLIDAY_MODE,
    ATTR_STATE_LOCKED,
    ATTR_STATE_SUMMER_MODE,
    ATTR_STATE_WINDOW_OPEN,
    DOMAIN as FB_DOMAIN,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_FRIENDLY_NAME,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import FritzDeviceClimateMock

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake_name"
MOCK_CONFIG = {
    FB_DOMAIN: [
        {
            CONF_HOST: "fake_host",
            CONF_PASSWORD: "fake_pass",
            CONF_USERNAME: "fake_user",
        }
    ]
}


@pytest.fixture(name="fritz")
def fritz_fixture():
    """Patch libraries."""
    with patch("homeassistant.components.fritzbox.socket") as socket1, patch(
        "homeassistant.components.fritzbox.config_flow.socket"
    ) as socket2, patch("homeassistant.components.fritzbox.Fritzhome") as fritz, patch(
        "homeassistant.components.fritzbox.config_flow.Fritzhome"
    ):
        socket1.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        socket2.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        yield fritz


async def setup_fritzbox(hass: HomeAssistantType, config: dict):
    """Set up mock AVM Fritz!Box."""
    assert await async_setup_component(hass, FB_DOMAIN, config) is True
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistantType, fritz: Mock):
    """Test setup of platform."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.attributes[ATTR_BATTERY_LEVEL] == 23
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake_name"
    assert state.attributes[ATTR_HVAC_MODES] == [HVAC_MODE_HEAT, HVAC_MODE_OFF]
    assert state.attributes[ATTR_MAX_TEMP] == 28
    assert state.attributes[ATTR_MIN_TEMP] == 8
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert state.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_COMFORT]
    assert state.attributes[ATTR_STATE_BATTERY_LOW] is True
    assert state.attributes[ATTR_STATE_DEVICE_LOCKED] == "fake_locked_device"
    assert state.attributes[ATTR_STATE_HOLIDAY_MODE] == "fake_holiday"
    assert state.attributes[ATTR_STATE_LOCKED] == "fake_locked"
    assert state.attributes[ATTR_STATE_SUMMER_MODE] == "fake_summer"
    assert state.attributes[ATTR_STATE_WINDOW_OPEN] == "fake_window"
    assert state.attributes[ATTR_TEMPERATURE] == 19.5
    assert state.state == HVAC_MODE_HEAT


async def test_update(hass: HomeAssistantType, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18
    assert state.attributes[ATTR_MAX_TEMP] == 28
    assert state.attributes[ATTR_MIN_TEMP] == 8
    assert state.attributes[ATTR_TEMPERATURE] == 19.5

    device.actual_temperature = 19
    device.target_temperature = 20

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)

    assert device.update.call_count == 1
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 19
    assert state.attributes[ATTR_TEMPERATURE] == 20


async def test_update_error(hass: HomeAssistantType, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceClimateMock()
    device.update.side_effect = HTTPError("Boom")
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    assert device.update.call_count == 0
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert device.update.call_count == 1
    assert fritz().login.call_count == 2
