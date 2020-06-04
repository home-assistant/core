"""test remote_rpi_gpio switch."""

import logging
import unittest

import homeassistant.components.remote_rpi_gpio as remote_rpi_gpio
from homeassistant.components.remote_rpi_gpio.switch import setup_switch
from homeassistant.setup import setup_component

from tests.async_mock import PropertyMock, patch
from tests.common import assert_setup_component, get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


def patch_led(led, invert_logic=False):
    """Patch a led for testing."""
    status = False
    active_high = not invert_logic

    def get_status(*args, **kwargs):
        _LOGGER.debug("status %s", status)
        return status

    def set_on(*args, **kwargs):
        nonlocal status
        _LOGGER.debug("turning on")
        status = active_high

    def set_off(*args, **kwargs):
        nonlocal status
        _LOGGER.debug("turning off")
        status = not active_high

    type(led).is_lit = PropertyMock(side_effect=get_status)
    led.on.side_effect = set_on
    led.off.side_effect = set_off

    return led


class TestRemoteRpiGpioSwitch(unittest.TestCase):
    """Test the remote module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch("homeassistant.components.remote_rpi_gpio.switch.LED")
    @patch("homeassistant.components.remote_rpi_gpio.switch.PiGPIOFactory")
    def test_switch_setup(self, LED, PiGPIOFactory):
        """Test setup with configuration missing required entries."""
        with assert_setup_component(1, "switch"):
            assert setup_component(
                self.hass,
                "switch",
                {
                    "switch": [
                        {
                            "platform": remote_rpi_gpio.DOMAIN,
                            "host": "127.0.0.127",
                            "ports": {17: "rpi_gpio17"},
                        }
                    ]
                },
            )

    @patch("homeassistant.components.remote_rpi_gpio.switch.LED")
    @patch("homeassistant.components.remote_rpi_gpio.switch.PiGPIOFactory")
    def test_switch_on(self, LED, PiGPIOFactory):
        """Test setup with configuration missing required entries."""
        invert_logic = False
        pi_switch = setup_switch("127.0.0.127", 17, "rpi_gpio17", invert_logic)
        assert pi_switch is not None

        pi_switch.hass = self.hass
        # pylint: disable=protected-access
        patch_led(pi_switch._switch, invert_logic)

        assert not pi_switch.is_on
        pi_switch.turn_on()
        assert pi_switch.is_on
        pi_switch.turn_off()
        assert not pi_switch.is_on
