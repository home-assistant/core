"""
tests.test_component_device_tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the device tracker compoments.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
from datetime import timedelta
import logging
import os

import homeassistant as ha
import homeassistant.loader as loader
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    STATE_HOME, STATE_NOT_HOME, ATTR_ENTITY_PICTURE, CONF_PLATFORM)
import homeassistant.components.device_tracker as device_tracker

from helpers import get_test_home_assistant


def setUpModule():   # pylint: disable=invalid-name
    """ Setup to ignore group errors. """
    logging.disable(logging.CRITICAL)


class TestComponentsDeviceTracker(unittest.TestCase):
    """ Tests homeassistant.components.device_tracker module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = get_test_home_assistant()
        loader.prepare(self.hass)

        self.known_dev_path = self.hass.config.path(
            device_tracker.KNOWN_DEVICES_FILE)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

        if os.path.isfile(self.known_dev_path):
            os.remove(self.known_dev_path)

    def test_is_on(self):
        """ Test is_on method. """
        entity_id = device_tracker.ENTITY_ID_FORMAT.format('test')

        self.hass.states.set(entity_id, STATE_HOME)

        self.assertTrue(device_tracker.is_on(self.hass, entity_id))

        self.hass.states.set(entity_id, STATE_NOT_HOME)

        self.assertFalse(device_tracker.is_on(self.hass, entity_id))

    def test_setup(self):
        """ Test setup method. """
        # Bogus config
        self.assertFalse(device_tracker.setup(self.hass, {}))

        self.assertFalse(
            device_tracker.setup(self.hass, {device_tracker.DOMAIN: {}}))

        # Test with non-existing component
        self.assertFalse(device_tracker.setup(
            self.hass, {device_tracker.DOMAIN: {CONF_PLATFORM: 'nonexisting'}}
        ))

        # Test with a bad known device file around
        with open(self.known_dev_path, 'w') as fil:
            fil.write("bad data\nbad data\n")

        self.assertFalse(device_tracker.setup(self.hass, {
            device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}
        }))

    def test_writing_known_devices_file(self):
        """ Test the device tracker class. """
        scanner = loader.get_component(
            'device_tracker.test').get_scanner(None, None)

        scanner.reset()

        scanner.come_home('DEV1')
        scanner.come_home('DEV2')

        self.assertTrue(device_tracker.setup(self.hass, {
            device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}
        }))

        # Ensure a new known devices file has been created.
        # Since the device_tracker uses a set internally we cannot
        # know what the order of the devices in the known devices file is.
        # To ensure all the three expected lines are there, we sort the file
        with open(self.known_dev_path) as fil:
            self.assertEqual(
                ['DEV1,unknown device,0,\n', 'DEV2,dev2,0,\n',
                 'device,name,track,picture\n'],
                sorted(fil))

        # Write one where we track dev1, dev2
        with open(self.known_dev_path, 'w') as fil:
            fil.write('device,name,track,picture\n')
            fil.write('DEV1,device 1,1,http://example.com/dev1.jpg\n')
            fil.write('DEV2,device 2,1,http://example.com/dev2.jpg\n')

        scanner.leave_home('DEV1')
        scanner.come_home('DEV3')

        self.hass.services.call(
            device_tracker.DOMAIN,
            device_tracker.SERVICE_DEVICE_TRACKER_RELOAD)

        self.hass.pool.block_till_done()

        dev1 = device_tracker.ENTITY_ID_FORMAT.format('device_1')
        dev2 = device_tracker.ENTITY_ID_FORMAT.format('device_2')
        dev3 = device_tracker.ENTITY_ID_FORMAT.format('DEV3')

        now = dt_util.utcnow()

        # Device scanner scans every 12 seconds. We need to sync our times to
        # be every 12 seconds or else the time_changed event will be ignored.
        nowAlmostMinimumGone = now + device_tracker.TIME_DEVICE_NOT_FOUND
        nowAlmostMinimumGone -= timedelta(
            seconds=12+(nowAlmostMinimumGone.second % 12))

        nowMinimumGone = now + device_tracker.TIME_DEVICE_NOT_FOUND
        nowMinimumGone += timedelta(seconds=12-(nowMinimumGone.second % 12))

        # Test initial is correct
        self.assertTrue(device_tracker.is_on(self.hass))
        self.assertFalse(device_tracker.is_on(self.hass, dev1))
        self.assertTrue(device_tracker.is_on(self.hass, dev2))
        self.assertIsNone(self.hass.states.get(dev3))

        self.assertEqual(
            'http://example.com/dev1.jpg',
            self.hass.states.get(dev1).attributes.get(ATTR_ENTITY_PICTURE))
        self.assertEqual(
            'http://example.com/dev2.jpg',
            self.hass.states.get(dev2).attributes.get(ATTR_ENTITY_PICTURE))

        # Test if dev3 got added to known dev file
        with open(self.known_dev_path) as fil:
            self.assertEqual('DEV3,dev3,0,\n', list(fil)[-1])

        # Change dev3 to track
        with open(self.known_dev_path, 'w') as fil:
            fil.write("device,name,track,picture\n")
            fil.write('DEV1,Device 1,1,http://example.com/picture.jpg\n')
            fil.write('DEV2,Device 2,1,http://example.com/picture.jpg\n')
            fil.write('DEV3,DEV3,1,\n')

        scanner.come_home('DEV1')
        scanner.leave_home('DEV2')

        # reload dev file
        self.hass.services.call(
            device_tracker.DOMAIN,
            device_tracker.SERVICE_DEVICE_TRACKER_RELOAD)

        self.hass.pool.block_till_done()

        # Test what happens if a device comes home and another leaves
        self.assertTrue(device_tracker.is_on(self.hass))
        self.assertTrue(device_tracker.is_on(self.hass, dev1))
        # Dev2 will still be home because of the error margin on time
        self.assertTrue(device_tracker.is_on(self.hass, dev2))
        # dev3 should be tracked now after we reload the known devices
        self.assertTrue(device_tracker.is_on(self.hass, dev3))

        self.assertIsNone(
            self.hass.states.get(dev3).attributes.get(ATTR_ENTITY_PICTURE))

        # Test if device leaves what happens, test the time span
        self.hass.bus.fire(
            ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: nowAlmostMinimumGone})

        self.hass.pool.block_till_done()

        self.assertTrue(device_tracker.is_on(self.hass))
        self.assertTrue(device_tracker.is_on(self.hass, dev1))
        # Dev2 will still be home because of the error time
        self.assertTrue(device_tracker.is_on(self.hass, dev2))
        self.assertTrue(device_tracker.is_on(self.hass, dev3))

        # Now test if gone for longer then error margin
        self.hass.bus.fire(
            ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: nowMinimumGone})

        self.hass.pool.block_till_done()

        self.assertTrue(device_tracker.is_on(self.hass))
        self.assertTrue(device_tracker.is_on(self.hass, dev1))
        self.assertFalse(device_tracker.is_on(self.hass, dev2))
        self.assertTrue(device_tracker.is_on(self.hass, dev3))
