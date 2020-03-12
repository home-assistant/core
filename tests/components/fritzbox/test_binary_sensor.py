"""Tests for samsungtv component."""
from datetime import timedelta

from asynctest import mock
from asynctest.mock import Mock, patch
import pytest
from requests.exceptions import HTTPError

from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import FritzDeviceBinarySensorMock

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
    device = FritzDeviceBinarySensorMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake_name"
    assert state.attributes[ATTR_DEVICE_CLASS] == "window"


async def test_update(hass: HomeAssistantType, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceBinarySensorMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    next_update = dt_util.utcnow() + timedelta(seconds=20)
    async_fire_time_changed(hass, next_update)
    assert device.update.call_count == 1


async def test_update_error(hass: HomeAssistantType, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceBinarySensorMock()
    device.update.side_effect = [mock.DEFAULT, HTTPError("Boom")]
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert fritz().login.call_count == 1
    next_update = dt_util.utcnow() + timedelta(seconds=20)
    async_fire_time_changed(hass, next_update)
    assert fritz().login.call_count == 2
