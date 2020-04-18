"""The tests for the litejet component."""
import logging
import unittest
from unittest import mock

from homeassistant import setup
from homeassistant.components import litejet
import homeassistant.components.switch as switch

from tests.common import get_test_home_assistant
from tests.components.switch import common

_LOGGER = logging.getLogger(__name__)

ENTITY_SWITCH = "switch.mock_switch_1"
ENTITY_SWITCH_NUMBER = 1
ENTITY_OTHER_SWITCH = "switch.mock_switch_2"
ENTITY_OTHER_SWITCH_NUMBER = 2


class TestLiteJetSwitch(unittest.TestCase):
    """Test the litejet component."""

    @mock.patch("homeassistant.components.litejet.LiteJet")
    def setup_method(self, method, mock_pylitejet):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.start()

        self.switch_pressed_callbacks = {}
        self.switch_released_callbacks = {}

        def get_switch_name(number):
            return f"Mock Switch #{number}"

        def on_switch_pressed(number, callback):
            self.switch_pressed_callbacks[number] = callback

        def on_switch_released(number, callback):
            self.switch_released_callbacks[number] = callback

        self.mock_lj = mock_pylitejet.return_value
        self.mock_lj.loads.return_value = range(0)
        self.mock_lj.button_switches.return_value = range(1, 3)
        self.mock_lj.all_switches.return_value = range(1, 6)
        self.mock_lj.scenes.return_value = range(0)
        self.mock_lj.get_switch_name.side_effect = get_switch_name
        self.mock_lj.on_switch_pressed.side_effect = on_switch_pressed
        self.mock_lj.on_switch_released.side_effect = on_switch_released

        config = {"litejet": {"port": "/dev/serial/by-id/mock-litejet"}}
        if method == self.test_include_switches_False:
            config["litejet"]["include_switches"] = False
        elif method != self.test_include_switches_unspecified:
            config["litejet"]["include_switches"] = True

        assert setup.setup_component(self.hass, litejet.DOMAIN, config)
        self.hass.block_till_done()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def switch(self):
        """Return the switch state."""
        return self.hass.states.get(ENTITY_SWITCH)

    def other_switch(self):
        """Return the other switch state."""
        return self.hass.states.get(ENTITY_OTHER_SWITCH)

    def test_include_switches_unspecified(self):
        """Test that switches are ignored by default."""
        self.mock_lj.button_switches.assert_not_called()
        self.mock_lj.all_switches.assert_not_called()

    def test_include_switches_False(self):
        """Test that switches can be explicitly ignored."""
        self.mock_lj.button_switches.assert_not_called()
        self.mock_lj.all_switches.assert_not_called()

    def test_on_off(self):
        """Test turning the switch on and off."""
        assert self.switch().state == "off"
        assert self.other_switch().state == "off"

        assert not switch.is_on(self.hass, ENTITY_SWITCH)

        common.turn_on(self.hass, ENTITY_SWITCH)
        self.hass.block_till_done()
        self.mock_lj.press_switch.assert_called_with(ENTITY_SWITCH_NUMBER)

        common.turn_off(self.hass, ENTITY_SWITCH)
        self.hass.block_till_done()
        self.mock_lj.release_switch.assert_called_with(ENTITY_SWITCH_NUMBER)

    def test_pressed_event(self):
        """Test handling an event from LiteJet."""
        # Switch 1
        _LOGGER.info(self.switch_pressed_callbacks[ENTITY_SWITCH_NUMBER])
        self.switch_pressed_callbacks[ENTITY_SWITCH_NUMBER]()
        self.hass.block_till_done()

        assert switch.is_on(self.hass, ENTITY_SWITCH)
        assert not switch.is_on(self.hass, ENTITY_OTHER_SWITCH)
        assert self.switch().state == "on"
        assert self.other_switch().state == "off"

        # Switch 2
        self.switch_pressed_callbacks[ENTITY_OTHER_SWITCH_NUMBER]()
        self.hass.block_till_done()

        assert switch.is_on(self.hass, ENTITY_OTHER_SWITCH)
        assert switch.is_on(self.hass, ENTITY_SWITCH)
        assert self.other_switch().state == "on"
        assert self.switch().state == "on"

    def test_released_event(self):
        """Test handling an event from LiteJet."""
        # Initial state is on.
        self.switch_pressed_callbacks[ENTITY_OTHER_SWITCH_NUMBER]()
        self.hass.block_till_done()

        assert switch.is_on(self.hass, ENTITY_OTHER_SWITCH)

        # Event indicates it is off now.

        self.switch_released_callbacks[ENTITY_OTHER_SWITCH_NUMBER]()
        self.hass.block_till_done()

        assert not switch.is_on(self.hass, ENTITY_OTHER_SWITCH)
        assert not switch.is_on(self.hass, ENTITY_SWITCH)
        assert self.other_switch().state == "off"
        assert self.switch().state == "off"
