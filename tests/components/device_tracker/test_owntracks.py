"""The tests for the Owntracks device tracker."""
import asyncio
import json
import unittest
from unittest.mock import patch

from tests.common import (assert_setup_component, fire_mqtt_message, mock_coro,
                          get_test_home_assistant, mock_mqtt_component,
                          mock_component)

import homeassistant.components.device_tracker.owntracks as owntracks
from homeassistant.setup import setup_component
from homeassistant.components import device_tracker
from homeassistant.const import CONF_PLATFORM, STATE_NOT_HOME
from homeassistant.util.async import run_coroutine_threadsafe

USER = 'greg'
DEVICE = 'phone'

LOCATION_TOPIC = 'owntracks/{}/{}'.format(USER, DEVICE)
EVENT_TOPIC = 'owntracks/{}/{}/event'.format(USER, DEVICE)
WAYPOINT_TOPIC = 'owntracks/{}/{}/waypoints'.format(USER, DEVICE)
USER_BLACKLIST = 'ram'
WAYPOINT_TOPIC_BLOCKED = 'owntracks/{}/{}/waypoints'.format(
    USER_BLACKLIST, DEVICE)

DEVICE_TRACKER_STATE = 'device_tracker.{}_{}'.format(USER, DEVICE)

IBEACON_DEVICE = 'keys'
REGION_TRACKER_STATE = 'device_tracker.beacon_{}'.format(IBEACON_DEVICE)

CONF_MAX_GPS_ACCURACY = 'max_gps_accuracy'
CONF_WAYPOINT_IMPORT = owntracks.CONF_WAYPOINT_IMPORT
CONF_WAYPOINT_WHITELIST = owntracks.CONF_WAYPOINT_WHITELIST
CONF_SECRET = owntracks.CONF_SECRET

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

WAYPOINTS_EXPORTED_MESSAGE = {
    "_type": "waypoints",
    "_creator": "test",
    "waypoints": [
        {
            "_type": "waypoint",
            "tst": 3,
            "lat": 47,
            "lon": 9,
            "rad": 10,
            "desc": "exp_wayp1"
        },
        {
            "_type": "waypoint",
            "tst": 4,
            "lat": 3,
            "lon": 9,
            "rad": 500,
            "desc": "exp_wayp2"
        }
    ]
}

WAYPOINTS_UPDATED_MESSAGE = {
    "_type": "waypoints",
    "_creator": "test",
    "waypoints": [
        {
            "_type": "waypoint",
            "tst": 4,
            "lat": 9,
            "lon": 47,
            "rad": 50,
            "desc": "exp_wayp1"
        },
    ]
}

WAYPOINT_ENTITY_NAMES = ['zone.greg_phone__exp_wayp1',
                         'zone.greg_phone__exp_wayp2',
                         'zone.ram_phone__exp_wayp1',
                         'zone.ram_phone__exp_wayp2']

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

BAD_JSON_PREFIX = '--$this is bad json#--'
BAD_JSON_SUFFIX = '** and it ends here ^^'

TEST_SECRET_KEY = 's3cretkey'
ENCRYPTED_LOCATION_MESSAGE = {
    # Encrypted version of LOCATION_MESSAGE using libsodium and TEST_SECRET_KEY
    '_type': 'encrypted',
    'data': ('qm1A83I6TVFRmH5343xy+cbex8jBBxDFkHRuJhELVKVRA/DgXcyKtghw'
             '9pOw75Lo4gHcyy2wV5CmkjrpKEBR7Qhye4AR0y7hOvlx6U/a3GuY1+W8'
             'I4smrLkwMvGgBOzXSNdVTzbFTHDvG3gRRaNHFkt2+5MsbH2Dd6CXmpzq'
             'DIfSN7QzwOevuvNIElii5MlFxI6ZnYIDYA/ZdnAXHEVsNIbyT2N0CXt3'
             'fTPzgGtFzsufx40EEUkC06J7QTJl7lLG6qaLW1cCWp86Vp0eL3vtZ6xq')}

MOCK_ENCRYPTED_LOCATION_MESSAGE = {
    # Mock-encrypted version of LOCATION_MESSAGE using pickle
    '_type': 'encrypted',
    'data': ('gANDCXMzY3JldGtleXEAQ6p7ImxvbiI6IDEuMCwgInQiOiAidSIsICJi'
             'YXR0IjogOTIsICJhY2MiOiA2MCwgInZlbCI6IDAsICJfdHlwZSI6ICJs'
             'b2NhdGlvbiIsICJ2YWMiOiA0LCAicCI6IDEwMS4zOTc3NTg0ODM4ODY3'
             'LCAidHN0IjogMSwgImxhdCI6IDIuMCwgImFsdCI6IDI3LCAiY29nIjog'
             'MjQ4LCAidGlkIjogInVzZXIifXEBhnECLg==')
}


class BaseMQTT(unittest.TestCase):
    """Base MQTT assert functions."""

    hass = None

    def send_message(self, topic, message, corrupt=False):
        """Test the sending of a message."""
        str_message = json.dumps(message)
        if corrupt:
            mod_message = BAD_JSON_PREFIX + str_message + BAD_JSON_SUFFIX
        else:
            mod_message = str_message
        fire_mqtt_message(self.hass, topic, mod_message)
        self.hass.block_till_done()

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


class TestDeviceTrackerOwnTracks(BaseMQTT):
    """Test the OwnTrack sensor."""

    # pylint: disable=invalid-name
    def setup_method(self, _):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)
        mock_component(self.hass, 'group')
        mock_component(self.hass, 'zone')

        patcher = patch('homeassistant.components.device_tracker.'
                        'DeviceTracker.async_update_config')
        patcher.start()
        self.addCleanup(patcher.stop)

        orig_context = owntracks.OwnTracksContext

        def store_context(*args):
            self.context = orig_context(*args)
            return self.context

        with patch('homeassistant.components.device_tracker.async_load_config',
                   return_value=mock_coro([])), \
                patch('homeassistant.components.device_tracker.'
                      'load_yaml_config_file', return_value=mock_coro({})), \
                patch.object(owntracks, 'OwnTracksContext', store_context), \
                assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    CONF_MAX_GPS_ACCURACY: 200,
                    CONF_WAYPOINT_IMPORT: True,
                    CONF_WAYPOINT_WHITELIST: ['jon', 'greg']
                }})

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

    def teardown_method(self, _):
        """Stop everything that was started."""
        self.hass.stop()

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

    def test_location_invalid_devid(self):  # pylint: disable=invalid-name
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
        self.assertFalse(self.context.regions_entered[USER])

    def test_event_with_spaces(self):
        """Test the entry event."""
        message = REGION_ENTER_MESSAGE.copy()
        message['desc'] = "inner 2"
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner 2')

        message = REGION_LEAVE_MESSAGE.copy()
        message['desc'] = "inner 2"
        self.send_message(EVENT_TOPIC, message)

        # Left clean zone state
        self.assertFalse(self.context.regions_entered[USER])

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
        self.assertFalse(self.context.regions_entered[USER])

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
        self.assertFalse(self.context.regions_entered[USER])

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

        for _ in range(0, 20):
            fire_mqtt_message(
                self.hass, EVENT_TOPIC, json.dumps(enter_message))
            fire_mqtt_message(
                self.hass, EVENT_TOPIC, json.dumps(exit_message))

        fire_mqtt_message(
            self.hass, EVENT_TOPIC, json.dumps(enter_message))

        self.hass.block_till_done()
        self.send_message(EVENT_TOPIC, exit_message)
        self.assertEqual(self.context.mobile_beacons_active['greg_phone'], [])

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

        self.assertEqual(self.context.mobile_beacons_active['greg_phone'], [])

    def test_waypoint_import_simple(self):
        """Test a simple import of list of waypoints."""
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINT_TOPIC, waypoints_message)
        # Check if it made it into states
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[0])
        self.assertTrue(wayp is not None)
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[1])
        self.assertTrue(wayp is not None)

    def test_waypoint_import_blacklist(self):
        """Test import of list of waypoints for blacklisted user."""
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINT_TOPIC_BLOCKED, waypoints_message)
        # Check if it made it into states
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[2])
        self.assertTrue(wayp is None)
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[3])
        self.assertTrue(wayp is None)

    def test_waypoint_import_no_whitelist(self):
        """Test import of list of waypoints with no whitelist set."""
        @asyncio.coroutine
        def mock_see(**kwargs):
            """Fake see method for owntracks."""
            return

        test_config = {
            CONF_PLATFORM: 'owntracks',
            CONF_MAX_GPS_ACCURACY: 200,
            CONF_WAYPOINT_IMPORT: True
        }
        run_coroutine_threadsafe(owntracks.async_setup_scanner(
            self.hass, test_config, mock_see), self.hass.loop).result()
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINT_TOPIC_BLOCKED, waypoints_message)
        # Check if it made it into states
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[2])
        self.assertTrue(wayp is not None)
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[3])
        self.assertTrue(wayp is not None)

    def test_waypoint_import_bad_json(self):
        """Test importing a bad JSON payload."""
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINT_TOPIC, waypoints_message, True)
        # Check if it made it into states
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[2])
        self.assertTrue(wayp is None)
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[3])
        self.assertTrue(wayp is None)

    def test_waypoint_import_existing(self):
        """Test importing a zone that exists."""
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINT_TOPIC, waypoints_message)
        # Get the first waypoint exported
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[0])
        # Send an update
        waypoints_message = WAYPOINTS_UPDATED_MESSAGE.copy()
        self.send_message(WAYPOINT_TOPIC, waypoints_message)
        new_wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[0])
        self.assertTrue(wayp == new_wayp)


def mock_cipher():
    """Return a dummy pickle-based cipher."""
    def mock_decrypt(ciphertext, key):
        """Decrypt/unpickle."""
        import pickle
        (mkey, plaintext) = pickle.loads(ciphertext)
        if key != mkey:
            raise ValueError()
        return plaintext
    return (len(TEST_SECRET_KEY), mock_decrypt)


class TestDeviceTrackerOwnTrackConfigs(BaseMQTT):
    """Test the OwnTrack sensor."""

    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)
        mock_component(self.hass, 'group')
        mock_component(self.hass, 'zone')

        patch_load = patch(
            'homeassistant.components.device_tracker.async_load_config',
            return_value=mock_coro([]))
        patch_load.start()
        self.addCleanup(patch_load.stop)

        patch_save = patch('homeassistant.components.device_tracker.'
                           'DeviceTracker.async_update_config')
        patch_save.start()
        self.addCleanup(patch_save.stop)

    def teardown_method(self, method):
        """Tear down resources."""
        self.hass.stop()

    @patch('homeassistant.components.device_tracker.owntracks.get_cipher',
           mock_cipher)
    def test_encrypted_payload(self):
        """Test encrypted payload."""
        with assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    CONF_SECRET: TEST_SECRET_KEY,
                }})
        self.send_message(LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
        self.assert_location_latitude(2.0)

    @patch('homeassistant.components.device_tracker.owntracks.get_cipher',
           mock_cipher)
    def test_encrypted_payload_topic_key(self):
        """Test encrypted payload with a topic key."""
        with assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    CONF_SECRET: {
                        LOCATION_TOPIC: TEST_SECRET_KEY,
                    }}})
        self.send_message(LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
        self.assert_location_latitude(2.0)

    @patch('homeassistant.components.device_tracker.owntracks.get_cipher',
           mock_cipher)
    def test_encrypted_payload_no_key(self):
        """Test encrypted payload with no key, ."""
        with assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    # key missing
                }})
        self.send_message(LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
        assert self.hass.states.get(DEVICE_TRACKER_STATE) is None

    @patch('homeassistant.components.device_tracker.owntracks.get_cipher',
           mock_cipher)
    def test_encrypted_payload_wrong_key(self):
        """Test encrypted payload with wrong key."""
        with assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    CONF_SECRET: 'wrong key',
                }})
        self.send_message(LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
        assert self.hass.states.get(DEVICE_TRACKER_STATE) is None

    @patch('homeassistant.components.device_tracker.owntracks.get_cipher',
           mock_cipher)
    def test_encrypted_payload_wrong_topic_key(self):
        """Test encrypted payload with wrong  topic key."""
        with assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    CONF_SECRET: {
                        LOCATION_TOPIC: 'wrong key'
                    }}})
        self.send_message(LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
        assert self.hass.states.get(DEVICE_TRACKER_STATE) is None

    @patch('homeassistant.components.device_tracker.owntracks.get_cipher',
           mock_cipher)
    def test_encrypted_payload_no_topic_key(self):
        """Test encrypted payload with no topic key."""
        with assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    CONF_SECRET: {
                        'owntracks/{}/{}'.format(USER, 'otherdevice'): 'foobar'
                    }}})
        self.send_message(LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
        assert self.hass.states.get(DEVICE_TRACKER_STATE) is None

    try:
        import libnacl
    except (ImportError, OSError):
        libnacl = None

    @unittest.skipUnless(libnacl, "libnacl/libsodium is not installed")
    def test_encrypted_payload_libsodium(self):
        """Test sending encrypted message payload."""
        with assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    CONF_SECRET: TEST_SECRET_KEY,
                    }})

        self.send_message(LOCATION_TOPIC, ENCRYPTED_LOCATION_MESSAGE)
        self.assert_location_latitude(2.0)
