"""The tests for the litejet component."""
import logging
import unittest
from unittest import mock

from homeassistant import setup
from homeassistant.components import litejet
import homeassistant.components.light as light

from tests.common import get_test_home_assistant
from tests.components.light import common

_LOGGER = logging.getLogger(__name__)

ENTITY_LIGHT = "light.mock_load_1"
ENTITY_LIGHT_NUMBER = 1
ENTITY_OTHER_LIGHT = "light.mock_load_2"
ENTITY_OTHER_LIGHT_NUMBER = 2


class TestLiteJetLight(unittest.TestCase):
    """Test the litejet component."""

    @mock.patch("homeassistant.components.litejet.LiteJet")
    def setup_method(self, method, mock_pylitejet):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.start()

        self.load_activated_callbacks = {}
        self.load_deactivated_callbacks = {}

        def get_load_name(number):
            return "Mock Load #" + str(number)

        def on_load_activated(number, callback):
            self.load_activated_callbacks[number] = callback

        def on_load_deactivated(number, callback):
            self.load_deactivated_callbacks[number] = callback

        self.mock_lj = mock_pylitejet.return_value
        self.mock_lj.loads.return_value = range(1, 3)
        self.mock_lj.button_switches.return_value = range(0)
        self.mock_lj.all_switches.return_value = range(0)
        self.mock_lj.scenes.return_value = range(0)
        self.mock_lj.get_load_level.return_value = 0
        self.mock_lj.get_load_name.side_effect = get_load_name
        self.mock_lj.on_load_activated.side_effect = on_load_activated
        self.mock_lj.on_load_deactivated.side_effect = on_load_deactivated

        assert setup.setup_component(
            self.hass,
            litejet.DOMAIN,
            {"litejet": {"port": "/dev/serial/by-id/mock-litejet"}},
        )
        self.hass.block_till_done()

        self.mock_lj.get_load_level.reset_mock()

    def light(self):
        """Test for main light entity."""
        return self.hass.states.get(ENTITY_LIGHT)

    def other_light(self):
        """Test the other light."""
        return self.hass.states.get(ENTITY_OTHER_LIGHT)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_on_brightness(self):
        """Test turning the light on with brightness."""
        assert self.light().state == "off"
        assert self.other_light().state == "off"

        assert not light.is_on(self.hass, ENTITY_LIGHT)

        common.turn_on(self.hass, ENTITY_LIGHT, brightness=102)
        self.hass.block_till_done()
        self.mock_lj.activate_load_at.assert_called_with(ENTITY_LIGHT_NUMBER, 39, 0)

    def test_on_off(self):
        """Test turning the light on and off."""
        assert self.light().state == "off"
        assert self.other_light().state == "off"

        assert not light.is_on(self.hass, ENTITY_LIGHT)

        common.turn_on(self.hass, ENTITY_LIGHT)
        self.hass.block_till_done()
        self.mock_lj.activate_load.assert_called_with(ENTITY_LIGHT_NUMBER)

        common.turn_off(self.hass, ENTITY_LIGHT)
        self.hass.block_till_done()
        self.mock_lj.deactivate_load.assert_called_with(ENTITY_LIGHT_NUMBER)

    def test_activated_event(self):
        """Test handling an event from LiteJet."""
        self.mock_lj.get_load_level.return_value = 99

        # Light 1

        _LOGGER.info(self.load_activated_callbacks[ENTITY_LIGHT_NUMBER])
        self.load_activated_callbacks[ENTITY_LIGHT_NUMBER]()
        self.hass.block_till_done()

        self.mock_lj.get_load_level.assert_called_once_with(ENTITY_LIGHT_NUMBER)

        assert light.is_on(self.hass, ENTITY_LIGHT)
        assert not light.is_on(self.hass, ENTITY_OTHER_LIGHT)
        assert self.light().state == "on"
        assert self.other_light().state == "off"
        assert self.light().attributes.get(light.ATTR_BRIGHTNESS) == 255

        # Light 2

        self.mock_lj.get_load_level.return_value = 40

        self.mock_lj.get_load_level.reset_mock()

        self.load_activated_callbacks[ENTITY_OTHER_LIGHT_NUMBER]()
        self.hass.block_till_done()

        self.mock_lj.get_load_level.assert_called_once_with(ENTITY_OTHER_LIGHT_NUMBER)

        assert light.is_on(self.hass, ENTITY_OTHER_LIGHT)
        assert light.is_on(self.hass, ENTITY_LIGHT)
        assert self.light().state == "on"
        assert self.other_light().state == "on"
        assert int(self.other_light().attributes[light.ATTR_BRIGHTNESS]) == 103

    def test_deactivated_event(self):
        """Test handling an event from LiteJet."""
        # Initial state is on.

        self.mock_lj.get_load_level.return_value = 99

        self.load_activated_callbacks[ENTITY_OTHER_LIGHT_NUMBER]()
        self.hass.block_till_done()

        assert light.is_on(self.hass, ENTITY_OTHER_LIGHT)

        # Event indicates it is off now.

        self.mock_lj.get_load_level.reset_mock()
        self.mock_lj.get_load_level.return_value = 0

        self.load_deactivated_callbacks[ENTITY_OTHER_LIGHT_NUMBER]()
        self.hass.block_till_done()

        # (Requesting the level is not strictly needed with a deactivated
        # event but the implementation happens to do it. This could be
        # changed to an assert_not_called in the future.)
        self.mock_lj.get_load_level.assert_called_with(ENTITY_OTHER_LIGHT_NUMBER)

        assert not light.is_on(self.hass, ENTITY_OTHER_LIGHT)
        assert not light.is_on(self.hass, ENTITY_LIGHT)
        assert self.light().state == "off"
        assert self.other_light().state == "off"
