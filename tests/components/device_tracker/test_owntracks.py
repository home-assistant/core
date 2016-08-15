"""The tests for the Owntracks device tracker."""
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

CONF_MAX_GPS_ACCURACY = 'max_gps_accuracy'

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

LOCATION_MESSAGE_INACCURATE = {
    'batt': 92,
    'cog': 248,
    'tid': 'user',
    'lon': 2.0,
    't': 'u',
    'alt': 27,
    'acc': 2000,
    'p': 101.3977584838867,
    'vac': 4,
    'lat': 6.0,
    '_type': 'location',
    'tst': 1,
    'vel': 0}

LOCATION_MESSAGE_ZERO_ACCURACY = {
    'batt': 92,
    'cog': 248,
    'tid': 'user',
    'lon': 2.0,
    't': 'u',
    'alt': 27,
    'acc': 0,
    'p': 101.3977584838867,
    'vac': 4,
    'lat': 6.0,
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

REGION_LEAVE_INACCURATE_MESSAGE = {
    'lon': 10.0,
    'event': 'leave',
    'tid': 'user',
    'desc': 'inner',
    'wtst': 1,
    't': 'b',
    'acc': 2000,
    'tst': 2,
    'lat': 20.0,
    '_type': 'transition'}


REGION_ENTER_ZERO_MESSAGE = {
    'lon': 1.0,
    'event': 'enter',
    'tid': 'user',
    'desc': 'inner',
    'wtst': 1,
    't': 'b',
    'acc': 0,
    'tst': 2,
    'lat': 2.0,
    '_type': 'transition'}

REGION_LEAVE_ZERO_MESSAGE = {
    'lon': 10.0,
    'event': 'leave',
    'tid': 'user',
    'desc': 'inner',
    'wtst': 1,
    't': 'b',
    'acc': 0,
    'tst': 2,
    'lat': 20.0,
    '_type': 'transition'}


class TestDeviceTrackerOwnTracks(unittest.TestCase):
    """Test the OwnTrack sensor."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)
        self.assertTrue(device_tracker.setup(self.hass, {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'owntracks',
                CONF_MAX_GPS_ACCURACY: 200
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

        # Clear state between teste
        self.hass.states.set(DEVICE_TRACKER_STATE, None)
        owntracks.REGIONS_ENTERED = defaultdict(list)
        owntracks.MOBILE_BEACONS_ACTIVE = defaultdict(list)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def send_message(self, topic, message):
        """Test the sending of a message."""
        fire_mqtt_message(
            self.hass, topic, json.dumps(message))
        self.hass.pool.block_till_done()

    def assert_location_state(self, location):
        """Test the assertion of a location state."""
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.state, location)

    def assert_location_latitude(self, latitude):
        """Test the assertion of a location latitude."""
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.attributes.get('latitude'), latitude)

    def assert_location_longitude(self, longitude):
        """Test the assertion of a location longitude."""
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.attributes.get('longitude'), longitude)

    def assert_location_accuracy(self, accuracy):
        """Test the assertion of a location accuracy."""
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.attributes.get('gps_accuracy'), accuracy)

    def assert_tracker_state(self, location):
        """Test the assertion of a tracker state."""
        state = self.hass.states.get(REGION_TRACKER_STATE)
        self.assertEqual(state.state, location)

    def assert_tracker_latitude(self, latitude):
        """Test the assertion of a tracker latitude."""
        state = self.hass.states.get(REGION_TRACKER_STATE)
        self.assertEqual(state.attributes.get('latitude'), latitude)

    def assert_tracker_accuracy(self, accuracy):
        """Test the assertion of a tracker accuracy."""
        state = self.hass.states.get(REGION_TRACKER_STATE)
        self.assertEqual(state.attributes.get('gps_accuracy'), accuracy)

    def test_location_invalid_devid(self):
        """Test the update of a location."""
        self.send_message('owntracks/paulus/nexus-5x', LOCATION_MESSAGE)

        state = self.hass.states.get('device_tracker.paulus_nexus5x')
        assert state.state == 'outer'

    def test_location_update(self):
        """Test the update of a location."""
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        self.assert_location_latitude(2.0)
        self.assert_location_accuracy(60.0)
        self.assert_location_state('outer')

    def test_location_inaccurate_gps(self):
        """Test the location for inaccurate GPS information."""
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE_INACCURATE)

        self.assert_location_latitude(2.0)
        self.assert_location_longitude(1.0)

    def test_location_zero_accuracy_gps(self):
        """Ignore the location for zero accuracy GPS information."""
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE_ZERO_ACCURACY)

        self.assert_location_latitude(2.0)
        self.assert_location_longitude(1.0)

    def test_event_entry_exit(self):
        """Test the entry event."""
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

    def test_event_with_spaces(self):
        """Test the entry event."""
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "inner 2"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner_2')

        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = "inner 2"
        self.send_message(EVENT_TOPIC, message)

        # Left clean zone state
        self.assertFalse(owntracks.REGIONS_ENTERED[USER])

    def test_event_entry_exit_inaccurate(self):
        """Test the event for inaccurate exit."""
        self.send_message(EVENT_TOPIC, REGION_ENTER_MESSAGE)

        # Enter uses the zone's gps co-ords
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)
        self.assert_location_state('inner')

        self.send_message(EVENT_TOPIC, REGION_LEAVE_INACCURATE_MESSAGE)

        # Exit doesn't use inaccurate gps
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)
        self.assert_location_state('inner')

        # But does exit region correctly
        self.assertFalse(owntracks.REGIONS_ENTERED[USER])

    def test_event_entry_exit_zero_accuracy(self):
        """Test entry/exit events with accuracy zero."""
        self.send_message(EVENT_TOPIC, REGION_ENTER_ZERO_MESSAGE)

        # Enter uses the zone's gps co-ords
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)
        self.assert_location_state('inner')

        self.send_message(EVENT_TOPIC, REGION_LEAVE_ZERO_MESSAGE)

        # Exit doesn't use zero gps
        self.assert_location_latitude(2.1)
        self.assert_location_accuracy(10.0)
        self.assert_location_state('inner')

        # But does exit region correctly
        self.assertFalse(owntracks.REGIONS_ENTERED[USER])

    def test_event_exit_outside_zone_sets_away(self):
        """Test the event for exit zone."""
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
        """Test the event for ordering."""
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
        """Test the event for wrong order."""
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

    def test_event_entry_unknown_zone(self):
        """Test the event for unknown zone."""
        # Just treat as location update
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "unknown"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_latitude(2.0)
        self.assert_location_state('outer')

    def test_event_exit_unknown_zone(self):
        """Test the event for unknown zone."""
        # Just treat as location update
        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = "unknown"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_latitude(2.0)
        self.assert_location_state('outer')

    def test_event_entry_zone_loading_dash(self):
        """Test the event for zone landing."""
        # Make sure the leading - is ignored
        # Ownracks uses this to switch on hold
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "-inner"
        self.send_message(EVENT_TOPIC, REGION_ENTER_MESSAGE)

        self.assert_location_state('inner')

    def test_mobile_enter_move_beacon(self):
        """Test the movement of a beacon."""
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
        """Test the enter and the exit of a region beacon."""
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
        """Test the exit move of a beacon."""
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

    def test_mobile_multiple_async_enter_exit(self):
        """Test the multiple entering."""
        # Test race condition
        enter_message = REGION_ENTER_MESSAGE.copy()
        enter_message['desc'] = IBEACON_DEVICE
        exit_message = REGION_LEAVE_MESSAGE.copy()
        exit_message['desc'] = IBEACON_DEVICE

        for i in range(0, 20):
            fire_mqtt_message(
                self.hass, EVENT_TOPIC, json.dumps(enter_message))
            fire_mqtt_message(
                self.hass, EVENT_TOPIC, json.dumps(exit_message))

        fire_mqtt_message(
            self.hass, EVENT_TOPIC, json.dumps(enter_message))

        self.hass.pool.block_till_done()
        self.send_message(EVENT_TOPIC, exit_message)
        self.assertEqual(owntracks.MOBILE_BEACONS_ACTIVE['greg_phone'], [])

    def test_mobile_multiple_enter_exit(self):
        """Test the multiple entering."""
        # Should only happen if the iphone dies
        enter_message = REGION_ENTER_MESSAGE.copy()
        enter_message['desc'] = IBEACON_DEVICE
        exit_message = REGION_LEAVE_MESSAGE.copy()
        exit_message['desc'] = IBEACON_DEVICE

        self.send_message(EVENT_TOPIC, enter_message)
        self.send_message(EVENT_TOPIC, enter_message)
        self.send_message(EVENT_TOPIC, exit_message)

        self.assertEqual(owntracks.MOBILE_BEACONS_ACTIVE['greg_phone'], [])
