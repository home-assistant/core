"""
tests.components.device_tracker.test_owntracks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Owntracks device tracker.
"""
import json
import os
import unittest

from collections import defaultdict

from homeassistant.components import device_tracker

from homeassistant.const import (STATE_NOT_HOME, CONF_PLATFORM)

import homeassistant.components.device_tracker.owntracks as owntracks

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)

USER = 'greg'
DEVICE = 'phone'

LOCATION_TOPIC = "owntracks/{}/{}".format(USER, DEVICE)
EVENT_TOPIC = "owntracks/{}/{}/event".format(USER, DEVICE)

DEVICE_TRACKER_STATE = "device_tracker.{}_{}".format(USER, DEVICE)

IBEACON_DEVICE = 'keys'
REGION_TRACKER_STATE = "device_tracker.beacon_{}".format(IBEACON_DEVICE)

LOCATION_MESSAGE = {
    'batt': 92,
    'cog': 248,
    'tid': 'user',
    'lon': 1.0,
    't': 'u',
    'alt': 27,
    'acc': 60,
    'p': 101.3977584838867,
    'vac': 4,
    'lat': 2.0,
    '_type': 'location',
    'tst': 1,
    'vel': 0}

REGION_ENTER_MESSAGE = {
    'lon': 1.0,
    'event': 'enter',
    'tid': 'user',
    'desc': 'inner',
    'wtst': 1,
    't': 'b',
    'acc': 60,
    'tst': 2,
    'lat': 2.0,
    '_type': 'transition'}


REGION_LEAVE_MESSAGE = {
    'lon': 1.0,
    'event': 'leave',
    'tid': 'user',
    'desc': 'inner',
    'wtst': 1,
    't': 'b',
    'acc': 60,
    'tst': 2,
    'lat': 2.0,
    '_type': 'transition'}


class TestDeviceTrackerOwnTracks(unittest.TestCase):
    """ Test the Template sensor. """

    def setup_method(self, method):
        """ Init needed objects. """
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)
        self.assertTrue(device_tracker.setup(self.hass, {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'owntracks'
            }}))

        self.hass.states.set(
            'zone.inner', 'zoning',
            {
                'name': 'zone',
                'latitude': 2.1,
                'longitude': 1.1,
                'radius': 10
            })

        self.hass.states.set(
            'zone.inner_2', 'zoning',
            {
                'name': 'zone',
                'latitude': 2.1,
                'longitude': 1.1,
                'radius': 10
            })

        self.hass.states.set(
            'zone.outer', 'zoning',
            {
                'name': 'zone',
                'latitude': 2.0,
                'longitude': 1.0,
                'radius': 100000
            })

        self.hass.states.set(
            'zone.passive', 'zoning',
            {
                'name': 'zone',
                'latitude': 3.0,
                'longitude': 1.0,
                'radius': 10,
                'passive': True
            })
        # Clear state between teste
        self.hass.states.set(DEVICE_TRACKER_STATE, None)
        owntracks.REGIONS_ENTERED = defaultdict(list)
        owntracks.MOBILE_BEACONS_ACTIVE = defaultdict(list)

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def send_message(self, topic, message):
        fire_mqtt_message(
            self.hass, topic, json.dumps(message))
        self.hass.pool.block_till_done()

    def assert_location_state(self, location):
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.state, location)

    def assert_location_latitude(self, latitude):
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.attributes.get('latitude'), latitude)

    def assert_location_accuracy(self, accuracy):
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.attributes.get('gps_accuracy'), accuracy)

    def assert_tracker_state(self, location):
        state = self.hass.states.get(REGION_TRACKER_STATE)
        self.assertEqual(state.state, location)

    def assert_tracker_latitude(self, latitude):
        state = self.hass.states.get(REGION_TRACKER_STATE)
        self.assertEqual(state.attributes.get('latitude'), latitude)

    def assert_tracker_accuracy(self, accuracy):
        state = self.hass.states.get(REGION_TRACKER_STATE)
        self.assertEqual(state.attributes.get('gps_accuracy'), accuracy)

    def test_location_update(self):
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        self.assert_location_latitude(2.0)
        self.assert_location_accuracy(60.0)
        self.assert_location_state('outer')

    def test_event_entry_exit(self):
        self.send_message(EVENT_TOPIC, REGION_ENTER_MESSAGE)

        # Enter uses the zone's gps co-ords
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)
        self.assert_location_state('inner')

        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        #  Updates ignored when in a zone
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)
        self.assert_location_state('inner')

        self.send_message(EVENT_TOPIC, REGION_LEAVE_MESSAGE)

        # Exit switches back to GPS
        self.assert_location_latitude(2.0)
        self.assert_location_accuracy(60.0)
        self.assert_location_state('outer')

        # Left clean zone state
        self.assertFalse(owntracks.REGIONS_ENTERED[USER])

    def test_event_exit_outside_zone_sets_away(self):
        self.send_message(EVENT_TOPIC, REGION_ENTER_MESSAGE)
        self.assert_location_state('inner')

        # Exit message far away GPS location
        message = REGION_LEAVE_MESSAGE.copy()
        message['lon'] = 90.1
        message['lat'] = 90.1
        self.send_message(EVENT_TOPIC, message)

        # Exit forces zone change to away
        self.assert_location_state(STATE_NOT_HOME)

    def test_event_entry_exit_right_order(self):
        # Enter inner zone
        self.send_message(EVENT_TOPIC, REGION_ENTER_MESSAGE)

        self.assert_location_state('inner')
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)

        # Enter inner2 zone
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "inner_2"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner_2')
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)

        # Exit inner_2 - should be in 'inner'
        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = "inner_2"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner')
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)

        # Exit inner - should be in 'outer'
        self.send_message(EVENT_TOPIC, REGION_LEAVE_MESSAGE)
        self.assert_location_state('outer')
        self.assert_location_latitude(2.0)
        self.assert_location_accuracy(60.0)

    def test_event_entry_exit_wrong_order(self):
        # Enter inner zone
        self.send_message(EVENT_TOPIC, REGION_ENTER_MESSAGE)
        self.assert_location_state('inner')

        # Enter inner2 zone
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "inner_2"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner_2')

        # Exit inner - should still be in 'inner_2'
        self.send_message(EVENT_TOPIC, REGION_LEAVE_MESSAGE)
        self.assert_location_state('inner_2')

        # Exit inner_2 - should be in 'outer'
        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = "inner_2"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('outer')

    def test_event_entry_exit_passive_zone(self):
        # Enter passive zone
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "passive"
        self.send_message(EVENT_TOPIC, message)

        # Should pick up gps put not zone
        self.assert_location_state('not_home')
        self.assert_location_latitude(3.0)
        self.assert_location_accuracy(10.0)

        # Enter inner2 zone
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "inner_2"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner_2')
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)

        # Exit inner_2 - should be in 'passive'
        # ie gps co-ords - but not zone
        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = "inner_2"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('not_home')
        self.assert_location_latitude(3.0)
        self.assert_location_accuracy(10.0)

        # Exit passive - should be in 'outer'
        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = "passive"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('outer')
        self.assert_location_latitude(2.0)
        self.assert_location_accuracy(60.0)

    def test_event_entry_unknown_zone(self):
        # Just treat as location update
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "unknown"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_latitude(2.0)
        self.assert_location_state('outer')

    def test_event_exit_unknown_zone(self):
        # Just treat as location update
        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = "unknown"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_latitude(2.0)
        self.assert_location_state('outer')

    def test_event_entry_zone_loading_dash(self):
        # Make sure the leading - is ignored
        # Ownracks uses this to switch on hold
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "-inner"
        self.send_message(EVENT_TOPIC, REGION_ENTER_MESSAGE)

        self.assert_location_state('inner')

    def test_mobile_enter_move_beacon(self):
        # Enter mobile beacon, should set location
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = IBEACON_DEVICE
        self.send_message(EVENT_TOPIC, message)

        self.assert_tracker_latitude(2.0)
        self.assert_tracker_state('outer')

        # Move should move beacon
        message = LOCATION_MESSAGE.copy()
        message['lat'] = "3.0"
        self.send_message(LOCATION_TOPIC, message)

        self.assert_tracker_latitude(3.0)
        self.assert_tracker_state(STATE_NOT_HOME)

    def test_mobile_enter_exit_region_beacon(self):
        # Start tracking beacon
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = IBEACON_DEVICE
        self.send_message(EVENT_TOPIC, message)
        self.assert_tracker_latitude(2.0)
        self.assert_tracker_state('outer')

        # Enter location should move beacon
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "inner_2"
        self.send_message(EVENT_TOPIC, message)

        self.assert_tracker_latitude(2.1)
        self.assert_tracker_state('inner_2')

        # Exit location should switch to gps
        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = "inner_2"
        self.send_message(EVENT_TOPIC, message)
        self.assert_tracker_latitude(2.0)

    def test_mobile_exit_move_beacon(self):
        # Start tracking beacon
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = IBEACON_DEVICE
        self.send_message(EVENT_TOPIC, message)
        self.assert_tracker_latitude(2.0)
        self.assert_tracker_state('outer')

        # Exit mobile beacon, should set location
        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = IBEACON_DEVICE
        message['lat'] = "3.0"
        self.send_message(EVENT_TOPIC, message)

        self.assert_tracker_latitude(3.0)

        # Move after exit should do nothing
        message = LOCATION_MESSAGE.copy()
        message['lat'] = "4.0"
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.assert_tracker_latitude(3.0)
