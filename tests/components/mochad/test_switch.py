"""The tests for the mochad switch platform."""

from unittest import mock

import pytest

from homeassistant.components import switch
from homeassistant.components.mochad import switch as mochad
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def pymochad_mock():
    """Mock pymochad."""
    with (
        mock.patch("homeassistant.components.mochad.switch.device"),
        mock.patch("homeassistant.components.mochad.switch.MochadException"),
    ):
        yield


@pytest.fixture
def switch_mock(hass):
    """Mock switch."""
    controller_mock = mock.MagicMock()
    dev_dict = {"address": "a1", "name": "fake_switch"}
    return mochad.MochadSwitch(hass, controller_mock, dev_dict)


async def test_setup_adds_proper_devices(hass: HomeAssistant) -> None:
    """Test if setup adds devices."""
    good_config = {
        "mochad": {},
        "switch": {
            "platform": "mochad",
            "devices": [{"name": "Switch1", "address": "a1"}],
        },
    }
    assert await async_setup_component(hass, switch.DOMAIN, good_config)


async def test_name(switch_mock) -> None:
    """Test the name."""
    assert switch_mock.name == "fake_switch"


async def test_turn_on(switch_mock) -> None:
    """Test turn_on."""
    switch_mock.turn_on()
    switch_mock.switch.send_cmd.assert_called_once_with("on")


async def test_turn_off(switch_mock) -> None:
    """Test turn_off."""
    switch_mock.turn_off()
    switch_mock.switch.send_cmd.assert_called_once_with("off")
