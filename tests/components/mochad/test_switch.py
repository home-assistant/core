"""The tests for the mochad switch platform."""
import unittest

import pytest

from homeassistant.components import switch
from homeassistant.components.mochad import switch as mochad
from homeassistant.setup import setup_component

import tests.async_mock as mock
from tests.common import get_test_home_assistant


@pytest.fixture(autouse=True)
def pymochad_mock():
    """Mock pymochad."""
    with mock.patch("homeassistant.components.mochad.switch.device"), mock.patch(
        "homeassistant.components.mochad.switch.MochadException"
    ):
        yield


class TestMochadSwitchSetup(unittest.TestCase):
    """Test the mochad switch."""

    PLATFORM = mochad
    COMPONENT = switch
    THING = "switch"

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch("homeassistant.components.mochad.switch.MochadSwitch")
    def test_setup_adds_proper_devices(self, mock_switch):
        """Test if setup adds devices."""
        good_config = {
            "mochad": {},
            "switch": {
                "platform": "mochad",
                "devices": [{"name": "Switch1", "address": "a1"}],
            },
        }
        assert setup_component(self.hass, switch.DOMAIN, good_config)


class TestMochadSwitch(unittest.TestCase):
    """Test for mochad switch platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        controller_mock = mock.MagicMock()
        dev_dict = {"address": "a1", "name": "fake_switch"}
        self.switch = mochad.MochadSwitch(self.hass, controller_mock, dev_dict)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_name(self):
        """Test the name."""
        assert "fake_switch" == self.switch.name

    def test_turn_on(self):
        """Test turn_on."""
        self.switch.turn_on()
        self.switch.switch.send_cmd.assert_called_once_with("on")

    def test_turn_off(self):
        """Test turn_off."""
        self.switch.turn_off()
        self.switch.switch.send_cmd.assert_called_once_with("off")
