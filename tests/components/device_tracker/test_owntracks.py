"""The tests for the Owntracks device tracker."""
import asyncio
import json
import unittest
from unittest.mock import patch

from tests.common import (
    assert_setup_component, fire_mqtt_message, mock_coro, mock_component,
    get_test_home_assistant, mock_mqtt_component)
import homeassistant.components.device_tracker.owntracks as owntracks
from homeassistant.setup import setup_component
from homeassistant.components import device_tracker
from homeassistant.const import CONF_PLATFORM, STATE_NOT_HOME
from homeassistant.util.async import run_coroutine_threadsafe

USER = 'greg'
DEVICE = 'phone'

LOCATION_TOPIC = 'owntracks/{}/{}'.format(USER, DEVICE)
EVENT_TOPIC = 'owntracks/{}/{}/event'.format(USER, DEVICE)
WAYPOINTS_TOPIC = 'owntracks/{}/{}/waypoints'.format(USER, DEVICE)
WAYPOINT_TOPIC = 'owntracks/{}/{}/waypoint'.format(USER, DEVICE)
USER_BLACKLIST = 'ram'
WAYPOINTS_TOPIC_BLOCKED = 'owntracks/{}/{}/waypoints'.format(
    USER_BLACKLIST, DEVICE)
LWT_TOPIC = 'owntracks/{}/{}/lwt'.format(USER, DEVICE)
BAD_TOPIC = 'owntracks/{}/{}/unsupported'.format(USER, DEVICE)

DEVICE_TRACKER_STATE = 'device_tracker.{}_{}'.format(USER, DEVICE)

IBEACON_DEVICE = 'keys'
MOBILE_BEACON_FMT = 'device_tracker.beacon_{}'

CONF_MAX_GPS_ACCURACY = 'max_gps_accuracy'
CONF_WAYPOINT_IMPORT = owntracks.CONF_WAYPOINT_IMPORT
CONF_WAYPOINT_WHITELIST = owntracks.CONF_WAYPOINT_WHITELIST
CONF_SECRET = owntracks.CONF_SECRET
CONF_MQTT_TOPIC = owntracks.CONF_MQTT_TOPIC
CONF_EVENTS_ONLY = owntracks.CONF_EVENTS_ONLY
CONF_REGION_MAPPING = owntracks.CONF_REGION_MAPPING

TEST_ZONE_LAT = 45.0
TEST_ZONE_LON = 90.0
TEST_ZONE_DEG_PER_M = 0.0000127
FIVE_M = TEST_ZONE_DEG_PER_M * 5.0


# Home Assistant Zones
INNER_ZONE = {
    'name': 'zone',
    'latitude': TEST_ZONE_LAT+0.1,
    'longitude': TEST_ZONE_LON+0.1,
    'radius': 50
}

OUTER_ZONE = {
    'name': 'zone',
    'latitude': TEST_ZONE_LAT,
    'longitude': TEST_ZONE_LON,
    'radius': 100000
}


def build_message(test_params, default_params):
    """Build a test message from overrides and another message."""
    new_params = default_params.copy()
    new_params.update(test_params)
    return new_params


# Default message parameters
DEFAULT_LOCATION_MESSAGE = {
    '_type': 'location',
    'lon': OUTER_ZONE['longitude'],
    'lat': OUTER_ZONE['latitude'],
    'acc': 60,
    'tid': 'user',
    't': 'u',
    'batt': 92,
    'cog': 248,
    'alt': 27,
    'p': 101.3977584838867,
    'vac': 4,
    'tst': 1,
    'vel': 0
}

# Owntracks will publish a transition when crossing
# a circular region boundary.
ZONE_EDGE = TEST_ZONE_DEG_PER_M * INNER_ZONE['radius']
DEFAULT_TRANSITION_MESSAGE = {
    '_type': 'transition',
    't': 'c',
    'lon': INNER_ZONE['longitude'],
    'lat': INNER_ZONE['latitude'] - ZONE_EDGE,
    'acc': 60,
    'event': 'enter',
    'tid': 'user',
    'desc': 'inner',
    'wtst': 1,
    'tst': 2
}

# iBeacons that are named the same as an HA zone
# are used to trigger enter and leave updates
# for that zone. In this case the "inner" zone.
#
# iBeacons that do not share an HA zone name
# are treated as mobile tracking devices for
# objects which can't track themselves e.g. keys.
#
# iBeacons are typically configured with the
# default lat/lon 0.0/0.0 and have acc 0.0 but
# regardless the reported location is not trusted.
#
# Owntracks will send both a location message
# for the device and an 'event' message for
# the beacon transition.
DEFAULT_BEACON_TRANSITION_MESSAGE = {
    '_type': 'transition',
    't': 'b',
    'lon': 0.0,
    'lat': 0.0,
    'acc': 0.0,
    'event': 'enter',
    'tid': 'user',
    'desc': 'inner',
    'wtst': 1,
    'tst': 2
}

# Location messages
LOCATION_MESSAGE = DEFAULT_LOCATION_MESSAGE

LOCATION_MESSAGE_INACCURATE = build_message(
    {'lat': INNER_ZONE['latitude'] - ZONE_EDGE,
     'lon': INNER_ZONE['longitude'] - ZONE_EDGE,
     'acc': 2000},
    LOCATION_MESSAGE)

LOCATION_MESSAGE_ZERO_ACCURACY = build_message(
    {'lat': INNER_ZONE['latitude'] - ZONE_EDGE,
     'lon': INNER_ZONE['longitude'] - ZONE_EDGE,
     'acc': 0},
    LOCATION_MESSAGE)

LOCATION_MESSAGE_NOT_HOME = build_message(
    {'lat': OUTER_ZONE['latitude'] - 2.0,
     'lon': INNER_ZONE['longitude'] - 2.0,
     'acc': 100},
    LOCATION_MESSAGE)

# Region GPS messages
REGION_GPS_ENTER_MESSAGE = DEFAULT_TRANSITION_MESSAGE

REGION_GPS_LEAVE_MESSAGE = build_message(
    {'lon': INNER_ZONE['longitude'] - ZONE_EDGE * 10,
     'lat': INNER_ZONE['latitude'] - ZONE_EDGE * 10,
     'event': 'leave'},
    DEFAULT_TRANSITION_MESSAGE)

REGION_GPS_ENTER_MESSAGE_INACCURATE = build_message(
    {'acc': 2000},
    REGION_GPS_ENTER_MESSAGE)

REGION_GPS_LEAVE_MESSAGE_INACCURATE = build_message(
    {'acc': 2000},
    REGION_GPS_LEAVE_MESSAGE)

REGION_GPS_ENTER_MESSAGE_ZERO = build_message(
    {'acc': 0},
    REGION_GPS_ENTER_MESSAGE)

REGION_GPS_LEAVE_MESSAGE_ZERO = build_message(
    {'acc': 0},
    REGION_GPS_LEAVE_MESSAGE)

REGION_GPS_LEAVE_MESSAGE_OUTER = build_message(
    {'lon': OUTER_ZONE['longitude'] - 2.0,
     'lat': OUTER_ZONE['latitude'] - 2.0,
     'desc': 'outer',
     'event': 'leave'},
    DEFAULT_TRANSITION_MESSAGE)

REGION_GPS_ENTER_MESSAGE_OUTER = build_message(
    {'lon': OUTER_ZONE['longitude'],
     'lat': OUTER_ZONE['latitude'],
     'desc': 'outer',
     'event': 'enter'},
    DEFAULT_TRANSITION_MESSAGE)

# Region Beacon messages
REGION_BEACON_ENTER_MESSAGE = DEFAULT_BEACON_TRANSITION_MESSAGE

REGION_BEACON_LEAVE_MESSAGE = build_message(
    {'event': 'leave'},
    DEFAULT_BEACON_TRANSITION_MESSAGE)

# Mobile Beacon messages
MOBILE_BEACON_ENTER_EVENT_MESSAGE = build_message(
    {'desc': IBEACON_DEVICE},
    DEFAULT_BEACON_TRANSITION_MESSAGE)

MOBILE_BEACON_LEAVE_EVENT_MESSAGE = build_message(
    {'desc': IBEACON_DEVICE,
     'event': 'leave'},
    DEFAULT_BEACON_TRANSITION_MESSAGE)

# Waypoint messages
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

WAYPOINT_MESSAGE = {
    "_type": "waypoint",
    "tst": 4,
    "lat": 9,
    "lon": 47,
    "rad": 50,
    "desc": "exp_wayp1"
}

WAYPOINT_ENTITY_NAMES = [
    'zone.greg_phone__exp_wayp1',
    'zone.greg_phone__exp_wayp2',
    'zone.ram_phone__exp_wayp1',
    'zone.ram_phone__exp_wayp2',
]

LWT_MESSAGE = {
    "_type": "lwt",
    "tst": 1
}

BAD_MESSAGE = {
    "_type": "unsupported",
    "tst": 1
}

BAD_JSON_PREFIX = '--$this is bad json#--'
BAD_JSON_SUFFIX = '** and it ends here ^^'


# def raise_on_not_implemented(hass, context, message):
def raise_on_not_implemented():
    """Throw NotImplemented."""
    raise NotImplementedError("oopsie")


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

    def assert_location_source_type(self, source_type):
        """Test the assertion of source_type."""
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.attributes.get('source_type'), source_type)


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
            'zone.inner', 'zoning', INNER_ZONE)

        self.hass.states.set(
            'zone.inner_2', 'zoning', INNER_ZONE)

        self.hass.states.set(
            'zone.outer', 'zoning', OUTER_ZONE)

        # Clear state between tests
        # NB: state "None" is not a state that is created by Device
        # so when we compare state to None in the tests this
        # is really checking that it is still in its original
        # test case state. See Device.async_update.
        self.hass.states.set(DEVICE_TRACKER_STATE, None)

    def teardown_method(self, _):
        """Stop everything that was started."""
        self.hass.stop()

    def assert_mobile_tracker_state(self, location, beacon=IBEACON_DEVICE):
        """Test the assertion of a mobile beacon tracker state."""
        dev_id = MOBILE_BEACON_FMT.format(beacon)
        state = self.hass.states.get(dev_id)
        self.assertEqual(state.state, location)

    def assert_mobile_tracker_latitude(self, latitude, beacon=IBEACON_DEVICE):
        """Test the assertion of a mobile beacon tracker latitude."""
        dev_id = MOBILE_BEACON_FMT.format(beacon)
        state = self.hass.states.get(dev_id)
        self.assertEqual(state.attributes.get('latitude'), latitude)

    def assert_mobile_tracker_accuracy(self, accuracy, beacon=IBEACON_DEVICE):
        """Test the assertion of a mobile beacon tracker accuracy."""
        dev_id = MOBILE_BEACON_FMT.format(beacon)
        state = self.hass.states.get(dev_id)
        self.assertEqual(state.attributes.get('gps_accuracy'), accuracy)

    def test_location_invalid_devid(self):  # pylint: disable=invalid-name
        """Test the update of a location."""
        self.send_message('owntracks/paulus/nexus-5x', LOCATION_MESSAGE)
        state = self.hass.states.get('device_tracker.paulus_nexus5x')
        assert state.state == 'outer'

    def test_location_update(self):
        """Test the update of a location."""
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        self.assert_location_latitude(LOCATION_MESSAGE['lat'])
        self.assert_location_accuracy(LOCATION_MESSAGE['acc'])
        self.assert_location_state('outer')

    def test_location_inaccurate_gps(self):
        """Test the location for inaccurate GPS information."""
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE_INACCURATE)

        # Ignored inaccurate GPS. Location remains at previous.
        self.assert_location_latitude(LOCATION_MESSAGE['lat'])
        self.assert_location_longitude(LOCATION_MESSAGE['lon'])

    def test_location_zero_accuracy_gps(self):
        """Ignore the location for zero accuracy GPS information."""
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE_ZERO_ACCURACY)

        # Ignored inaccurate GPS. Location remains at previous.
        self.assert_location_latitude(LOCATION_MESSAGE['lat'])
        self.assert_location_longitude(LOCATION_MESSAGE['lon'])

    # ------------------------------------------------------------------------
    # GPS based event entry / exit testing

    def test_event_gps_entry_exit(self):
        """Test the entry event."""
        # Entering the owntracks circular region named "inner"
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)

        # Enter uses the zone's gps co-ords
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        #  Updates ignored when in a zone
        #  note that LOCATION_MESSAGE is actually pretty far
        #  from INNER_ZONE and has good accuracy. I haven't
        #  received a transition message though so I'm still
        #  associated with the inner zone regardless of GPS.
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)

        # Exit switches back to GPS
        self.assert_location_latitude(REGION_GPS_LEAVE_MESSAGE['lat'])
        self.assert_location_accuracy(REGION_GPS_LEAVE_MESSAGE['acc'])
        self.assert_location_state('outer')

        # Left clean zone state
        self.assertFalse(self.context.regions_entered[USER])

        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        # Now sending a location update moves me again.
        self.assert_location_latitude(LOCATION_MESSAGE['lat'])
        self.assert_location_accuracy(LOCATION_MESSAGE['acc'])

    def test_event_gps_with_spaces(self):
        """Test the entry event."""
        message = build_message({'desc': "inner 2"},
                                REGION_GPS_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner 2')

        message = build_message({'desc': "inner 2"},
                                REGION_GPS_LEAVE_MESSAGE)
        self.send_message(EVENT_TOPIC, message)

        # Left clean zone state
        self.assertFalse(self.context.regions_entered[USER])

    def test_event_gps_entry_inaccurate(self):
        """Test the event for inaccurate entry."""
        # Set location to the outer zone.
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE_INACCURATE)

        # I enter the zone even though the message GPS was inaccurate.
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

    def test_event_gps_entry_exit_inaccurate(self):
        """Test the event for inaccurate exit."""
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)

        # Enter uses the zone's gps co-ords
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_INACCURATE)

        # Exit doesn't use inaccurate gps
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

        # But does exit region correctly
        self.assertFalse(self.context.regions_entered[USER])

    def test_event_gps_entry_exit_zero_accuracy(self):
        """Test entry/exit events with accuracy zero."""
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE_ZERO)

        # Enter uses the zone's gps co-ords
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_ZERO)

        # Exit doesn't use zero gps
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

        # But does exit region correctly
        self.assertFalse(self.context.regions_entered[USER])

    def test_event_gps_exit_outside_zone_sets_away(self):
        """Test the event for exit zone."""
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
        self.assert_location_state('inner')

        # Exit message far away GPS location
        message = build_message(
            {'lon': 90.0,
             'lat': 90.0},
            REGION_GPS_LEAVE_MESSAGE)
        self.send_message(EVENT_TOPIC, message)

        # Exit forces zone change to away
        self.assert_location_state(STATE_NOT_HOME)

    def test_event_gps_entry_exit_right_order(self):
        """Test the event for ordering."""
        # Enter inner zone
        # Set location to the outer zone.
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
        self.assert_location_state('inner')

        # Enter inner2 zone
        message = build_message(
            {'desc': "inner_2"},
            REGION_GPS_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner_2')

        # Exit inner_2 - should be in 'inner'
        message = build_message(
            {'desc': "inner_2"},
            REGION_GPS_LEAVE_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner')

        # Exit inner - should be in 'outer'
        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
        self.assert_location_latitude(REGION_GPS_LEAVE_MESSAGE['lat'])
        self.assert_location_accuracy(REGION_GPS_LEAVE_MESSAGE['acc'])
        self.assert_location_state('outer')

    def test_event_gps_entry_exit_wrong_order(self):
        """Test the event for wrong order."""
        # Enter inner zone
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
        self.assert_location_state('inner')

        # Enter inner2 zone
        message = build_message(
            {'desc': "inner_2"},
            REGION_GPS_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner_2')

        # Exit inner - should still be in 'inner_2'
        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
        self.assert_location_state('inner_2')

        # Exit inner_2 - should be in 'outer'
        message = build_message(
            {'desc': "inner_2"},
            REGION_GPS_LEAVE_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_latitude(REGION_GPS_LEAVE_MESSAGE['lat'])
        self.assert_location_accuracy(REGION_GPS_LEAVE_MESSAGE['acc'])
        self.assert_location_state('outer')

    def test_event_gps_entry_unknown_zone(self):
        """Test the event for unknown zone."""
        # Just treat as location update
        message = build_message(
            {'desc': "unknown"},
            REGION_GPS_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_latitude(REGION_GPS_ENTER_MESSAGE['lat'])
        self.assert_location_state('inner')

    def test_event_gps_exit_unknown_zone(self):
        """Test the event for unknown zone."""
        # Just treat as location update
        message = build_message(
            {'desc': "unknown"},
            REGION_GPS_LEAVE_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_latitude(REGION_GPS_LEAVE_MESSAGE['lat'])
        self.assert_location_state('outer')

    def test_event_entry_zone_loading_dash(self):
        """Test the event for zone landing."""
        # Make sure the leading - is ignored
        # Owntracks uses this to switch on hold
        message = build_message(
            {'desc': "-inner"},
            REGION_GPS_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner')

    def test_events_only_on(self):
        """Test events_only config suppresses location updates."""
        # Sending a location message that is not home
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)
        self.assert_location_state(STATE_NOT_HOME)

        self.context.events_only = True

        # Enter and Leave messages
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE_OUTER)
        self.assert_location_state('outer')
        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_OUTER)
        self.assert_location_state(STATE_NOT_HOME)

        # Sending a location message that is inside outer zone
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        # Ignored location update. Location remains at previous.
        self.assert_location_state(STATE_NOT_HOME)

    def test_events_only_off(self):
        """Test when events_only is False."""
        # Sending a location message that is not home
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)
        self.assert_location_state(STATE_NOT_HOME)

        self.context.events_only = False

        # Enter and Leave messages
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE_OUTER)
        self.assert_location_state('outer')
        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_OUTER)
        self.assert_location_state(STATE_NOT_HOME)

        # Sending a location message that is inside outer zone
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        # Location update processed
        self.assert_location_state('outer')

    def test_event_source_type_entry_exit(self):
        """Test the entry and exit events of source type."""
        # Entering the owntracks circular region named "inner"
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)

        # source_type should be gps when entering using gps.
        self.assert_location_source_type('gps')

        # owntracks shouldn't send beacon events with acc = 0
        self.send_message(EVENT_TOPIC, build_message(
            {'acc': 1}, REGION_BEACON_ENTER_MESSAGE))

        # We should be able to enter a beacon zone even inside a gps zone
        self.assert_location_source_type('bluetooth_le')

        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)

        # source_type should be gps when leaving using gps.
        self.assert_location_source_type('gps')

        # owntracks shouldn't send beacon events with acc = 0
        self.send_message(EVENT_TOPIC, build_message(
            {'acc': 1}, REGION_BEACON_LEAVE_MESSAGE))

        self.assert_location_source_type('bluetooth_le')

    # Region Beacon based event entry / exit testing

    def test_event_region_entry_exit(self):
        """Test the entry event."""
        # Seeing a beacon named "inner"
        self.send_message(EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)

        # Enter uses the zone's gps co-ords
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        #  Updates ignored when in a zone
        #  note that LOCATION_MESSAGE is actually pretty far
        #  from INNER_ZONE and has good accuracy. I haven't
        #  received a transition message though so I'm still
        #  associated with the inner zone regardless of GPS.
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

        self.send_message(EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)

        # Exit switches back to GPS but the beacon has no coords
        # so I am still located at the center of the inner region
        # until I receive a location update.
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

        # Left clean zone state
        self.assertFalse(self.context.regions_entered[USER])

        # Now sending a location update moves me again.
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.assert_location_latitude(LOCATION_MESSAGE['lat'])
        self.assert_location_accuracy(LOCATION_MESSAGE['acc'])

    def test_event_region_with_spaces(self):
        """Test the entry event."""
        message = build_message({'desc': "inner 2"},
                                REGION_BEACON_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner 2')

        message = build_message({'desc': "inner 2"},
                                REGION_BEACON_LEAVE_MESSAGE)
        self.send_message(EVENT_TOPIC, message)

        # Left clean zone state
        self.assertFalse(self.context.regions_entered[USER])

    def test_event_region_entry_exit_right_order(self):
        """Test the event for ordering."""
        # Enter inner zone
        # Set location to the outer zone.
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        # See 'inner' region beacon
        self.send_message(EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
        self.assert_location_state('inner')

        # See 'inner_2' region beacon
        message = build_message(
            {'desc': "inner_2"},
            REGION_BEACON_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner_2')

        # Exit inner_2 - should be in 'inner'
        message = build_message(
            {'desc': "inner_2"},
            REGION_BEACON_LEAVE_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner')

        # Exit inner - should be in 'outer'
        self.send_message(EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)

        # I have not had an actual location update yet and my
        # coordinates are set to the center of the last region I
        # entered which puts me in the inner zone.
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner')

    def test_event_region_entry_exit_wrong_order(self):
        """Test the event for wrong order."""
        # Enter inner zone
        self.send_message(EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
        self.assert_location_state('inner')

        # Enter inner2 zone
        message = build_message(
            {'desc': "inner_2"},
            REGION_BEACON_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner_2')

        # Exit inner - should still be in 'inner_2'
        self.send_message(EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)
        self.assert_location_state('inner_2')

        # Exit inner_2 - should be in 'outer'
        message = build_message(
            {'desc': "inner_2"},
            REGION_BEACON_LEAVE_MESSAGE)
        self.send_message(EVENT_TOPIC, message)

        # I have not had an actual location update yet and my
        # coordinates are set to the center of the last region I
        # entered which puts me in the inner_2 zone.
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_accuracy(INNER_ZONE['radius'])
        self.assert_location_state('inner_2')

    def test_event_beacon_unknown_zone_no_location(self):
        """Test the event for unknown zone."""
        # A beacon which does not match a HA zone is the
        # definition of a mobile beacon. In this case, "unknown"
        # will be turned into device_tracker.beacon_unknown and
        # that will be tracked at my current location. Except
        # in this case my Device hasn't had a location message
        # yet so it's in an odd state where it has state.state
        # None and no GPS coords so set the beacon to.

        message = build_message(
            {'desc': "unknown"},
            REGION_BEACON_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)

        # My current state is None because I haven't seen a
        # location message or a GPS or Region # Beacon event
        # message. None is the state the test harness set for
        # the Device during test case setup.
        self.assert_location_state('None')

        # home is the state of a Device constructed through
        # the normal code path on it's first observation with
        # the conditions I pass along.
        self.assert_mobile_tracker_state('home', 'unknown')

    def test_event_beacon_unknown_zone(self):
        """Test the event for unknown zone."""
        # A beacon which does not match a HA zone is the
        # definition of a mobile beacon. In this case, "unknown"
        # will be turned into device_tracker.beacon_unknown and
        # that will be tracked at my current location. First I
        # set my location so that my state is 'outer'

        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.assert_location_state('outer')

        message = build_message(
            {'desc': "unknown"},
            REGION_BEACON_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)

        # My state is still outer and now the unknown beacon
        # has joined me at outer.
        self.assert_location_state('outer')
        self.assert_mobile_tracker_state('outer', 'unknown')

    def test_event_beacon_entry_zone_loading_dash(self):
        """Test the event for beacon zone landing."""
        # Make sure the leading - is ignored
        # Owntracks uses this to switch on hold

        message = build_message(
            {'desc': "-inner"},
            REGION_BEACON_ENTER_MESSAGE)
        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner')

    # ------------------------------------------------------------------------
    # Mobile Beacon based event entry / exit testing

    def test_mobile_enter_move_beacon(self):
        """Test the movement of a beacon."""
        # I am in the outer zone.
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        # I see the 'keys' beacon. I set the location of the
        # beacon_keys tracker to my current device location.
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)

        self.assert_mobile_tracker_latitude(LOCATION_MESSAGE['lat'])
        self.assert_mobile_tracker_state('outer')

        # Location update to outside of defined zones.
        # I am now 'not home' and neither are my keys.
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)

        self.assert_location_state(STATE_NOT_HOME)
        self.assert_mobile_tracker_state(STATE_NOT_HOME)

        not_home_lat = LOCATION_MESSAGE_NOT_HOME['lat']
        self.assert_location_latitude(not_home_lat)
        self.assert_mobile_tracker_latitude(not_home_lat)

    def test_mobile_enter_exit_region_beacon(self):
        """Test the enter and the exit of a mobile beacon."""
        # I am in the outer zone.
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        # I see a new mobile beacon
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
        self.assert_mobile_tracker_latitude(OUTER_ZONE['latitude'])
        self.assert_mobile_tracker_state('outer')

        # GPS enter message should move beacon
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)

        self.assert_mobile_tracker_latitude(INNER_ZONE['latitude'])
        self.assert_mobile_tracker_state(REGION_GPS_ENTER_MESSAGE['desc'])

        # Exit inner zone to outer zone should move beacon to
        # center of outer zone
        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
        self.assert_mobile_tracker_latitude(REGION_GPS_LEAVE_MESSAGE['lat'])
        self.assert_mobile_tracker_state('outer')

    def test_mobile_exit_move_beacon(self):
        """Test the exit move of a beacon."""
        # I am in the outer zone.
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)

        # I see a new mobile beacon
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
        self.assert_mobile_tracker_latitude(OUTER_ZONE['latitude'])
        self.assert_mobile_tracker_state('outer')

        # Exit mobile beacon, should set location
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)

        self.assert_mobile_tracker_latitude(OUTER_ZONE['latitude'])
        self.assert_mobile_tracker_state('outer')

        # Move after exit should do nothing
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)
        self.assert_mobile_tracker_latitude(OUTER_ZONE['latitude'])
        self.assert_mobile_tracker_state('outer')

    def test_mobile_multiple_async_enter_exit(self):
        """Test the multiple entering."""
        # Test race condition
        for _ in range(0, 20):
            fire_mqtt_message(
                self.hass, EVENT_TOPIC,
                json.dumps(MOBILE_BEACON_ENTER_EVENT_MESSAGE))
            fire_mqtt_message(
                self.hass, EVENT_TOPIC,
                json.dumps(MOBILE_BEACON_LEAVE_EVENT_MESSAGE))

        fire_mqtt_message(
            self.hass, EVENT_TOPIC,
            json.dumps(MOBILE_BEACON_ENTER_EVENT_MESSAGE))

        self.hass.block_till_done()
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)
        self.assertEqual(len(self.context.mobile_beacons_active['greg_phone']),
                         0)

    def test_mobile_multiple_enter_exit(self):
        """Test the multiple entering."""
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)

        self.assertEqual(len(self.context.mobile_beacons_active['greg_phone']),
                         0)

    def test_complex_movement(self):
        """Test a complex sequence representative of real-world use."""
        # I am in the outer zone.
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.assert_location_state('outer')

        # gps to inner location and event, as actually happens with OwnTracks
        location_message = build_message(
            {'lat': REGION_GPS_ENTER_MESSAGE['lat'],
             'lon': REGION_GPS_ENTER_MESSAGE['lon']},
            LOCATION_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_state('inner')

        # region beacon enter inner event and location as actually happens
        # with OwnTracks
        location_message = build_message(
            {'lat': location_message['lat'] + FIVE_M,
             'lon': location_message['lon'] + FIVE_M},
            LOCATION_MESSAGE)
        self.send_message(EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_state('inner')

        # see keys mobile beacon and location message as actually happens
        location_message = build_message(
            {'lat': location_message['lat'] + FIVE_M,
             'lon': location_message['lon'] + FIVE_M},
            LOCATION_MESSAGE)
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_mobile_tracker_latitude(INNER_ZONE['latitude'])
        self.assert_location_state('inner')
        self.assert_mobile_tracker_state('inner')

        # Slightly odd, I leave the location by gps before I lose
        # sight of the region beacon. This is also a little odd in
        # that my GPS coords are now in the 'outer' zone but I did not
        # "enter" that zone when I started up so my location is not
        # the center of OUTER_ZONE, but rather just my GPS location.

        # gps out of inner event and location
        location_message = build_message(
            {'lat': REGION_GPS_LEAVE_MESSAGE['lat'],
             'lon': REGION_GPS_LEAVE_MESSAGE['lon']},
            LOCATION_MESSAGE)
        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_latitude(REGION_GPS_LEAVE_MESSAGE['lat'])
        self.assert_mobile_tracker_latitude(REGION_GPS_LEAVE_MESSAGE['lat'])
        self.assert_location_state('outer')
        self.assert_mobile_tracker_state('outer')

        # region beacon leave inner
        location_message = build_message(
            {'lat': location_message['lat'] - FIVE_M,
             'lon': location_message['lon'] - FIVE_M},
            LOCATION_MESSAGE)
        self.send_message(EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_latitude(location_message['lat'])
        self.assert_mobile_tracker_latitude(location_message['lat'])
        self.assert_location_state('outer')
        self.assert_mobile_tracker_state('outer')

        # lose keys mobile beacon
        lost_keys_location_message = build_message(
            {'lat': location_message['lat'] - FIVE_M,
             'lon': location_message['lon'] - FIVE_M},
            LOCATION_MESSAGE)
        self.send_message(LOCATION_TOPIC, lost_keys_location_message)
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)
        self.assert_location_latitude(lost_keys_location_message['lat'])
        self.assert_mobile_tracker_latitude(lost_keys_location_message['lat'])
        self.assert_location_state('outer')
        self.assert_mobile_tracker_state('outer')

        # gps leave outer
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)
        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_OUTER)
        self.assert_location_latitude(LOCATION_MESSAGE_NOT_HOME['lat'])
        self.assert_mobile_tracker_latitude(lost_keys_location_message['lat'])
        self.assert_location_state('not_home')
        self.assert_mobile_tracker_state('outer')

        # location move not home
        location_message = build_message(
            {'lat': LOCATION_MESSAGE_NOT_HOME['lat'] - FIVE_M,
             'lon': LOCATION_MESSAGE_NOT_HOME['lon'] - FIVE_M},
            LOCATION_MESSAGE_NOT_HOME)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_latitude(location_message['lat'])
        self.assert_mobile_tracker_latitude(lost_keys_location_message['lat'])
        self.assert_location_state('not_home')
        self.assert_mobile_tracker_state('outer')

    def test_complex_movement_sticky_keys_beacon(self):
        """Test a complex sequence which was previously broken."""
        # I am not_home
        self.send_message(LOCATION_TOPIC, LOCATION_MESSAGE)
        self.assert_location_state('outer')

        # gps to inner location and event, as actually happens with OwnTracks
        location_message = build_message(
            {'lat': REGION_GPS_ENTER_MESSAGE['lat'],
             'lon': REGION_GPS_ENTER_MESSAGE['lon']},
            LOCATION_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.send_message(EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_state('inner')

        # see keys mobile beacon and location message as actually happens
        location_message = build_message(
            {'lat': location_message['lat'] + FIVE_M,
             'lon': location_message['lon'] + FIVE_M},
            LOCATION_MESSAGE)
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_mobile_tracker_latitude(INNER_ZONE['latitude'])
        self.assert_location_state('inner')
        self.assert_mobile_tracker_state('inner')

        # region beacon enter inner event and location as actually happens
        # with OwnTracks
        location_message = build_message(
            {'lat': location_message['lat'] + FIVE_M,
             'lon': location_message['lon'] + FIVE_M},
            LOCATION_MESSAGE)
        self.send_message(EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_state('inner')

        # This sequence of moves would cause keys to follow
        # greg_phone around even after the OwnTracks sent
        # a mobile beacon 'leave' event for the keys.
        # leave keys
        self.send_message(LOCATION_TOPIC, location_message)
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)
        self.assert_location_state('inner')
        self.assert_mobile_tracker_state('inner')

        # leave inner region beacon
        self.send_message(EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_state('inner')
        self.assert_mobile_tracker_state('inner')

        # enter inner region beacon
        self.send_message(EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_latitude(INNER_ZONE['latitude'])
        self.assert_location_state('inner')

        # enter keys
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_state('inner')
        self.assert_mobile_tracker_state('inner')

        # leave keys
        self.send_message(LOCATION_TOPIC, location_message)
        self.send_message(EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)
        self.assert_location_state('inner')
        self.assert_mobile_tracker_state('inner')

        # leave inner region beacon
        self.send_message(EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)
        self.send_message(LOCATION_TOPIC, location_message)
        self.assert_location_state('inner')
        self.assert_mobile_tracker_state('inner')

        # GPS leave inner region, I'm in the 'outer' region now
        # but on GPS coords
        leave_location_message = build_message(
            {'lat': REGION_GPS_LEAVE_MESSAGE['lat'],
             'lon': REGION_GPS_LEAVE_MESSAGE['lon']},
            LOCATION_MESSAGE)
        self.send_message(EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
        self.send_message(LOCATION_TOPIC, leave_location_message)
        self.assert_location_state('outer')
        self.assert_mobile_tracker_state('inner')
        self.assert_location_latitude(REGION_GPS_LEAVE_MESSAGE['lat'])
        self.assert_mobile_tracker_latitude(INNER_ZONE['latitude'])

    def test_waypoint_import_simple(self):
        """Test a simple import of list of waypoints."""
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINTS_TOPIC, waypoints_message)
        # Check if it made it into states
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[0])
        self.assertTrue(wayp is not None)
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[1])
        self.assertTrue(wayp is not None)

    def test_waypoint_import_blacklist(self):
        """Test import of list of waypoints for blacklisted user."""
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINTS_TOPIC_BLOCKED, waypoints_message)
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
            CONF_WAYPOINT_IMPORT: True,
            CONF_MQTT_TOPIC: 'owntracks/#',
        }
        run_coroutine_threadsafe(owntracks.async_setup_scanner(
            self.hass, test_config, mock_see), self.hass.loop).result()
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINTS_TOPIC_BLOCKED, waypoints_message)
        # Check if it made it into states
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[2])
        self.assertTrue(wayp is not None)
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[3])
        self.assertTrue(wayp is not None)

    def test_waypoint_import_bad_json(self):
        """Test importing a bad JSON payload."""
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINTS_TOPIC, waypoints_message, True)
        # Check if it made it into states
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[2])
        self.assertTrue(wayp is None)
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[3])
        self.assertTrue(wayp is None)

    def test_waypoint_import_existing(self):
        """Test importing a zone that exists."""
        waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
        self.send_message(WAYPOINTS_TOPIC, waypoints_message)
        # Get the first waypoint exported
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[0])
        # Send an update
        waypoints_message = WAYPOINTS_UPDATED_MESSAGE.copy()
        self.send_message(WAYPOINTS_TOPIC, waypoints_message)
        new_wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[0])
        self.assertTrue(wayp == new_wayp)

    def test_single_waypoint_import(self):
        """Test single waypoint message."""
        waypoint_message = WAYPOINT_MESSAGE.copy()
        self.send_message(WAYPOINT_TOPIC, waypoint_message)
        wayp = self.hass.states.get(WAYPOINT_ENTITY_NAMES[0])
        self.assertTrue(wayp is not None)

    def test_not_implemented_message(self):
        """Handle not implemented message type."""
        patch_handler = patch('homeassistant.components.device_tracker.'
                              'owntracks.async_handle_not_impl_msg',
                              return_value=mock_coro(False))
        patch_handler.start()
        self.assertFalse(self.send_message(LWT_TOPIC, LWT_MESSAGE))
        patch_handler.stop()

    def test_unsupported_message(self):
        """Handle not implemented message type."""
        patch_handler = patch('homeassistant.components.device_tracker.'
                              'owntracks.async_handle_unsupported_msg',
                              return_value=mock_coro(False))
        patch_handler.start()
        self.assertFalse(self.send_message(BAD_TOPIC, BAD_MESSAGE))
        patch_handler.stop()


def generate_ciphers(secret):
    """Generate test ciphers for the DEFAULT_LOCATION_MESSAGE."""
    # libnacl ciphertext generation will fail if the module
    # cannot be imported. However, the test for decryption
    # also relies on this library and won't be run without it.
    import json
    import pickle
    import base64

    try:
        from libnacl import crypto_secretbox_KEYBYTES as KEYLEN
        from libnacl.secret import SecretBox
        key = secret.encode("utf-8")[:KEYLEN].ljust(KEYLEN, b'\0')
        ctxt = base64.b64encode(SecretBox(key).encrypt(
                  json.dumps(DEFAULT_LOCATION_MESSAGE).encode("utf-8"))
                  ).decode("utf-8")
    except (ImportError, OSError):
        ctxt = ''

    mctxt = base64.b64encode(
        pickle.dumps(
            (secret.encode("utf-8"),
             json.dumps(DEFAULT_LOCATION_MESSAGE).encode("utf-8"))
        )
    ).decode("utf-8")
    return ctxt, mctxt


TEST_SECRET_KEY = 's3cretkey'

CIPHERTEXT, MOCK_CIPHERTEXT = generate_ciphers(TEST_SECRET_KEY)

ENCRYPTED_LOCATION_MESSAGE = {
    # Encrypted version of LOCATION_MESSAGE using libsodium and TEST_SECRET_KEY
    '_type': 'encrypted',
    'data': CIPHERTEXT
}

MOCK_ENCRYPTED_LOCATION_MESSAGE = {
    # Mock-encrypted version of LOCATION_MESSAGE using pickle
    '_type': 'encrypted',
    'data': MOCK_CIPHERTEXT
}


def mock_cipher():
    """Return a dummy pickle-based cipher."""
    def mock_decrypt(ciphertext, key):
        """Decrypt/unpickle."""
        import pickle
        (mkey, plaintext) = pickle.loads(ciphertext)
        if key != mkey:
            raise ValueError()
        return plaintext
    return len(TEST_SECRET_KEY), mock_decrypt


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
        self.assert_location_latitude(LOCATION_MESSAGE['lat'])

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
        self.assert_location_latitude(LOCATION_MESSAGE['lat'])

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
        self.assert_location_latitude(LOCATION_MESSAGE['lat'])

    def test_customized_mqtt_topic(self):
        """Test subscribing to a custom mqtt topic."""
        with assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    CONF_MQTT_TOPIC: 'mytracks/#',
                    }})

        topic = 'mytracks/{}/{}'.format(USER, DEVICE)

        self.send_message(topic, LOCATION_MESSAGE)
        self.assert_location_latitude(LOCATION_MESSAGE['lat'])

    def test_region_mapping(self):
        """Test region to zone mapping."""
        with assert_setup_component(1, device_tracker.DOMAIN):
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'owntracks',
                    CONF_REGION_MAPPING: {
                        'foo': 'inner'
                    },
                    }})

        self.hass.states.set(
            'zone.inner', 'zoning', INNER_ZONE)

        message = build_message({'desc': 'foo'}, REGION_GPS_ENTER_MESSAGE)
        self.assertEqual(message['desc'], 'foo')

        self.send_message(EVENT_TOPIC, message)
        self.assert_location_state('inner')
