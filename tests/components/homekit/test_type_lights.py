"""Test different accessory types: Lights."""
import unittest

from homeassistant.core import callback
from homeassistant.components.homekit.type_lights import Light
from homeassistant.components.light import (
    DOMAIN, ATTR_BRIGHTNESS, ATTR_BRIGHTNESS_PCT, ATTR_RGB_COLOR,
    SUPPORT_BRIGHTNESS, SUPPORT_RGB_COLOR)
from homeassistant.const import (
    ATTR_DOMAIN, ATTR_ENTITY_ID, ATTR_SERVICE, ATTR_SERVICE_DATA,
    ATTR_SUPPORTED_FEATURES, EVENT_CALL_SERVICE, SERVICE_TURN_ON,
    SERVICE_TURN_OFF, STATE_ON, STATE_OFF, STATE_UNKNOWN)

from tests.common import get_test_home_assistant


class TestHomekitLights(unittest.TestCase):
    """Test class for all accessory types regarding lights."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.events = []

        @callback
        def record_event(event):
            """Track called event."""
            self.events.append(event)

        self.hass.bus.listen(EVENT_CALL_SERVICE, record_event)

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_light_basic(self):
        """Test light with char state."""
        entity_id = 'light.demo'
        self.hass.states.set(entity_id, STATE_ON,
                             {ATTR_SUPPORTED_FEATURES: 0})
        acc = Light(self.hass, entity_id, 'Light', aid=2)
        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 5)  # Lightbulb
        self.assertEqual(acc.char_on.value, 0)

        acc.run()
        self.hass.block_till_done()
        self.assertEqual(acc.char_on.value, 1)

        self.hass.states.set(entity_id, STATE_OFF,
                             {ATTR_SUPPORTED_FEATURES: 0})
        self.hass.block_till_done()
        self.assertEqual(acc.char_on.value, 0)

        self.hass.states.set(entity_id, STATE_UNKNOWN)
        self.hass.block_till_done()
        self.assertEqual(acc.char_on.value, 0)

        # Set from HomeKit
        acc.char_on.set_value(True)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], SERVICE_TURN_ON)

        acc.char_on.set_value(False)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], SERVICE_TURN_OFF)

        # Remove entity
        self.hass.states.remove(entity_id)
        self.hass.block_till_done()

    def test_light_brightness(self):
        """Test light with brightness."""
        entity_id = 'light.demo'
        self.hass.states.set(entity_id, STATE_ON, {
            ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS, ATTR_BRIGHTNESS: 255})
        acc = Light(self.hass, entity_id, 'Light', aid=2)
        self.assertEqual(acc.char_brightness.value, 0)

        acc.run()
        self.hass.block_till_done()
        self.assertEqual(acc.char_brightness.value, 100)

        self.hass.states.set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 102})
        self.hass.block_till_done()
        self.assertEqual(acc.char_brightness.value, 40)

        # Set from HomeKit
        acc.char_brightness.set_value(20)
        acc.char_on.set_value(1)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], SERVICE_TURN_ON)
        print(self.events[0].data)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA], {
                ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS_PCT: 20})

    def test_light_rgb_color(self):
        """Test light with rgb_color."""
        entity_id = 'light.demo'
        self.hass.states.set(entity_id, STATE_ON, {
            ATTR_SUPPORTED_FEATURES: SUPPORT_RGB_COLOR,
            ATTR_RGB_COLOR: (120, 20, 255)})
        acc = Light(self.hass, entity_id, 'Light', aid=2)
        self.assertEqual(acc.char_hue.value, 0)
        self.assertEqual(acc.char_saturation.value, 75)

        acc.run()
        self.hass.block_till_done()
        self.assertEqual(acc.char_hue.value, 265.532)
        self.assertEqual(acc.char_saturation.value, 92.157)

        # Set from HomeKit
        acc.char_hue.set_value(145)
        acc.char_saturation.set_value(75)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], SERVICE_TURN_ON)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA], {
                ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (63, 255, 143)})
