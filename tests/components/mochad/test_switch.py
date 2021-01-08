"""The tests for the mochad switch platform."""
import unittest.mock as mock

import pytest

from homeassistant.components import switch
from homeassistant.components.mochad import switch as mochad
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def pymochad_mock():
    """Mock pymochad."""
    with mock.patch("homeassistant.components.mochad.switch.device"), mock.patch(
        "homeassistant.components.mochad.switch.MochadException"
    ):
        yield


@pytest.fixture
def switch_mock(hass):
    """Mock switch."""
    controller_mock = mock.MagicMock()
    dev_dict = {"address": "a1", "name": "fake_switch"}
    return mochad.MochadSwitch(hass, controller_mock, dev_dict)


async def test_setup_adds_proper_devices(hass):
    """Test if setup adds devices."""
    good_config = {
        "mochad": {},
        "switch": {
            "platform": "mochad",
            "devices": [{"name": "Switch1", "address": "a1"}],
        },
    }
    assert await async_setup_component(hass, switch.DOMAIN, good_config)


async def test_name(switch_mock):
    """Test the name."""
    assert "fake_switch" == switch_mock.name


async def test_turn_on(switch_mock):
    """Test turn_on."""
    switch_mock.turn_on()
    switch_mock.switch.send_cmd.assert_called_once_with("on")


async def test_turn_off(switch_mock):
    """Test turn_off."""
    switch_mock.turn_off()
    switch_mock.switch.send_cmd.assert_called_once_with("off")
