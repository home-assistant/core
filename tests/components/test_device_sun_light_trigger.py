"""The tests device sun light trigger component."""
# pylint: disable=too-many-public-methods,protected-access
import os
import unittest

from homeassistant.bootstrap import setup_component
import homeassistant.loader as loader
from homeassistant.const import CONF_PLATFORM, STATE_HOME, STATE_NOT_HOME
from homeassistant.components import (
    device_tracker, light, sun, device_sun_light_trigger)
from homeassistant.helpers import event_decorators

from tests.common import (
    get_test_config_dir, get_test_home_assistant, ensure_sun_risen,
    ensure_sun_set)


KNOWN_DEV_YAML_PATH = os.path.join(get_test_config_dir(),
                                   device_tracker.YAML_DEVICES)


def setUpModule():   # pylint: disable=invalid-name
    """Write a device tracker known devices file to be used."""
    device_tracker.update_config(
        KNOWN_DEV_YAML_PATH, 'device_1', device_tracker.Device(
            None, None, True, 'device_1', 'DEV1',
            picture='http://example.com/dev1.jpg'))

    device_tracker.update_config(
        KNOWN_DEV_YAML_PATH, 'device_2', device_tracker.Device(
            None, None, True, 'device_2', 'DEV2',
            picture='http://example.com/dev2.jpg'))


def tearDownModule():   # pylint: disable=invalid-name
    """Remove device tracker known devices file."""
    os.remove(KNOWN_DEV_YAML_PATH)


class TestDeviceSunLightTrigger(unittest.TestCase):
    """Test the device sun light trigger module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        event_decorators.HASS = self.hass

        self.scanner = loader.get_component(
            'device_tracker.test').get_scanner(None, None)

        self.scanner.reset()
        self.scanner.come_home('DEV1')

        loader.get_component('light.test').init()

        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN, {
            device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}
        }))

        self.assertTrue(setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {CONF_PLATFORM: 'test'}
        }))

        self.assertTrue(setup_component(self.hass, sun.DOMAIN, {
            sun.DOMAIN: {sun.CONF_ELEVATION: 0}}))

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()
        event_decorators.HASS = None

    def test_lights_on_when_sun_sets(self):
        """Test lights go on when there is someone home and the sun sets."""
        self.assertTrue(setup_component(
            self.hass, device_sun_light_trigger.DOMAIN, {
                device_sun_light_trigger.DOMAIN: {}}))

        ensure_sun_risen(self.hass)
        light.turn_off(self.hass)

        self.hass.block_till_done()

        ensure_sun_set(self.hass)
        self.hass.block_till_done()

        self.assertTrue(light.is_on(self.hass))

    def test_lights_turn_off_when_everyone_leaves(self): \
            # pylint: disable=invalid-name
        """Test lights turn off when everyone leaves the house."""
        light.turn_on(self.hass)

        self.hass.block_till_done()

        self.assertTrue(setup_component(
            self.hass, device_sun_light_trigger.DOMAIN, {
                device_sun_light_trigger.DOMAIN: {}}))

        self.hass.states.set(device_tracker.ENTITY_ID_ALL_DEVICES,
                             STATE_NOT_HOME)

        self.hass.block_till_done()

        self.assertFalse(light.is_on(self.hass))

    def test_lights_turn_on_when_coming_home_after_sun_set(self): \
            # pylint: disable=invalid-name
        """Test lights turn on when coming home after sun set."""
        light.turn_off(self.hass)
        ensure_sun_set(self.hass)

        self.hass.block_till_done()

        self.assertTrue(setup_component(
            self.hass, device_sun_light_trigger.DOMAIN, {
                device_sun_light_trigger.DOMAIN: {}}))

        self.hass.states.set(
            device_tracker.ENTITY_ID_FORMAT.format('device_2'), STATE_HOME)

        self.hass.block_till_done()
        self.assertTrue(light.is_on(self.hass))
