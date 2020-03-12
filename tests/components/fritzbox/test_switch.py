"""Tests for samsungtv component."""
from datetime import timedelta

from asynctest import mock
from asynctest.mock import Mock, patch
import pytest
from requests.exceptions import HTTPError

from homeassistant.components.fritzbox.const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    ATTR_TEMPERATURE_UNIT,
    ATTR_TOTAL_CONSUMPTION,
    ATTR_TOTAL_CONSUMPTION_UNIT,
    DOMAIN as FB_DOMAIN,
)
from homeassistant.components.switch import ATTR_CURRENT_POWER_W, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    ENERGY_KILO_WATT_HOUR,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    TEMP_CELSIUS,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import FritzDeviceSwitchMock

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
    """Set up mock Samsung TV."""
    assert await async_setup_component(hass, FB_DOMAIN, config) is True
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistantType, fritz: Mock):
    """Test setup of platform."""
    device = FritzDeviceSwitchMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.attributes[ATTR_CURRENT_POWER_W] == 5.678
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake_name"
    assert state.attributes[ATTR_STATE_DEVICE_LOCKED] is True
    assert state.attributes[ATTR_STATE_LOCKED] is True
    assert state.attributes[ATTR_TEMPERATURE] == "135"
    assert state.attributes[ATTR_TEMPERATURE_UNIT] == TEMP_CELSIUS
    assert state.attributes[ATTR_TOTAL_CONSUMPTION] == "1.234"
    assert state.attributes[ATTR_TOTAL_CONSUMPTION_UNIT] == ENERGY_KILO_WATT_HOUR


async def test_turn_on(hass: HomeAssistantType, fritz: Mock):
    """Test turn device on."""
    device = FritzDeviceSwitchMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_switch_state_on.call_count == 1


async def test_turn_off(hass: HomeAssistantType, fritz: Mock):
    """Test turn device off."""
    device = FritzDeviceSwitchMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_switch_state_off.call_count == 1


async def test_update_error(hass: HomeAssistantType, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceSwitchMock()
    device.update.side_effect = [mock.DEFAULT, HTTPError("Boom")]
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert fritz().login.call_count == 1
    next_update = dt_util.utcnow() + timedelta(seconds=20)
    async_fire_time_changed(hass, next_update)
    assert fritz().login.call_count == 2
