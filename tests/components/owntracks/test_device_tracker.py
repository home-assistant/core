"""The tests for the Owntracks device tracker."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components import owntracks
from homeassistant.const import STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import ClientSessionGenerator

USER = "greg"
DEVICE = "phone"

LOCATION_TOPIC = f"owntracks/{USER}/{DEVICE}"
EVENT_TOPIC = f"owntracks/{USER}/{DEVICE}/event"
WAYPOINTS_TOPIC = f"owntracks/{USER}/{DEVICE}/waypoints"
WAYPOINT_TOPIC = f"owntracks/{USER}/{DEVICE}/waypoint"
USER_BLACKLIST = "ram"
WAYPOINTS_TOPIC_BLOCKED = f"owntracks/{USER_BLACKLIST}/{DEVICE}/waypoints"
LWT_TOPIC = f"owntracks/{USER}/{DEVICE}/lwt"
BAD_TOPIC = f"owntracks/{USER}/{DEVICE}/unsupported"

DEVICE_TRACKER_STATE = f"device_tracker.{USER}_{DEVICE}"

IBEACON_DEVICE = "keys"
MOBILE_BEACON_FMT = "device_tracker.beacon_{}"

CONF_MAX_GPS_ACCURACY = "max_gps_accuracy"
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
    "name": "zone",
    "latitude": TEST_ZONE_LAT + 0.1,
    "longitude": TEST_ZONE_LON + 0.1,
    "radius": 50,
}

OUTER_ZONE = {
    "name": "zone",
    "latitude": TEST_ZONE_LAT,
    "longitude": TEST_ZONE_LON,
    "radius": 100000,
}


def build_message(test_params, default_params):
    """Build a test message from overrides and another message."""
    new_params = default_params.copy()
    new_params.update(test_params)
    return new_params


# Default message parameters
DEFAULT_LOCATION_MESSAGE = {
    "_type": "location",
    "lon": OUTER_ZONE["longitude"],
    "lat": OUTER_ZONE["latitude"],
    "acc": 60,
    "tid": "user",
    "t": "u",
    "batt": 92,
    "cog": 248,
    "alt": 27,
    "p": 101.3977584838867,
    "vac": 4,
    "tst": 1,
    "vel": 0,
}

# Owntracks will publish a transition when crossing
# a circular region boundary.
ZONE_EDGE = TEST_ZONE_DEG_PER_M * INNER_ZONE["radius"]
DEFAULT_TRANSITION_MESSAGE = {
    "_type": "transition",
    "t": "c",
    "lon": INNER_ZONE["longitude"],
    "lat": INNER_ZONE["latitude"] - ZONE_EDGE,
    "acc": 60,
    "event": "enter",
    "tid": "user",
    "desc": "inner",
    "wtst": 1,
    "tst": 2,
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
    "_type": "transition",
    "t": "b",
    "lon": 0.0,
    "lat": 0.0,
    "acc": 0.0,
    "event": "enter",
    "tid": "user",
    "desc": "inner",
    "wtst": 1,
    "tst": 2,
}

# Location messages
LOCATION_MESSAGE = DEFAULT_LOCATION_MESSAGE

LOCATION_MESSAGE_INACCURATE = build_message(
    {
        "lat": INNER_ZONE["latitude"] - ZONE_EDGE,
        "lon": INNER_ZONE["longitude"] - ZONE_EDGE,
        "acc": 2000,
    },
    LOCATION_MESSAGE,
)

LOCATION_MESSAGE_ZERO_ACCURACY = build_message(
    {
        "lat": INNER_ZONE["latitude"] - ZONE_EDGE,
        "lon": INNER_ZONE["longitude"] - ZONE_EDGE,
        "acc": 0,
    },
    LOCATION_MESSAGE,
)

LOCATION_MESSAGE_NOT_HOME = build_message(
    {
        "lat": OUTER_ZONE["latitude"] - 2.0,
        "lon": INNER_ZONE["longitude"] - 2.0,
        "acc": 100,
    },
    LOCATION_MESSAGE,
)

# Region GPS messages
REGION_GPS_ENTER_MESSAGE = DEFAULT_TRANSITION_MESSAGE

REGION_GPS_LEAVE_MESSAGE = build_message(
    {
        "lon": INNER_ZONE["longitude"] - ZONE_EDGE * 10,
        "lat": INNER_ZONE["latitude"] - ZONE_EDGE * 10,
        "event": "leave",
    },
    DEFAULT_TRANSITION_MESSAGE,
)

REGION_GPS_ENTER_MESSAGE_INACCURATE = build_message(
    {"acc": 2000}, REGION_GPS_ENTER_MESSAGE
)

REGION_GPS_LEAVE_MESSAGE_INACCURATE = build_message(
    {"acc": 2000}, REGION_GPS_LEAVE_MESSAGE
)

REGION_GPS_ENTER_MESSAGE_ZERO = build_message({"acc": 0}, REGION_GPS_ENTER_MESSAGE)

REGION_GPS_LEAVE_MESSAGE_ZERO = build_message({"acc": 0}, REGION_GPS_LEAVE_MESSAGE)

REGION_GPS_LEAVE_MESSAGE_OUTER = build_message(
    {
        "lon": OUTER_ZONE["longitude"] - 2.0,
        "lat": OUTER_ZONE["latitude"] - 2.0,
        "desc": "outer",
        "event": "leave",
    },
    DEFAULT_TRANSITION_MESSAGE,
)

REGION_GPS_ENTER_MESSAGE_OUTER = build_message(
    {
        "lon": OUTER_ZONE["longitude"],
        "lat": OUTER_ZONE["latitude"],
        "desc": "outer",
        "event": "enter",
    },
    DEFAULT_TRANSITION_MESSAGE,
)

# Region Beacon messages
REGION_BEACON_ENTER_MESSAGE = DEFAULT_BEACON_TRANSITION_MESSAGE

REGION_BEACON_LEAVE_MESSAGE = build_message(
    {"event": "leave"}, DEFAULT_BEACON_TRANSITION_MESSAGE
)

# Mobile Beacon messages
MOBILE_BEACON_ENTER_EVENT_MESSAGE = build_message(
    {"desc": IBEACON_DEVICE}, DEFAULT_BEACON_TRANSITION_MESSAGE
)

MOBILE_BEACON_LEAVE_EVENT_MESSAGE = build_message(
    {"desc": IBEACON_DEVICE, "event": "leave"}, DEFAULT_BEACON_TRANSITION_MESSAGE
)

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
            "desc": "exp_wayp1",
        },
        {
            "_type": "waypoint",
            "tst": 4,
            "lat": 3,
            "lon": 9,
            "rad": 500,
            "desc": "exp_wayp2",
        },
    ],
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
            "desc": "exp_wayp1",
        }
    ],
}

WAYPOINT_MESSAGE = {
    "_type": "waypoint",
    "tst": 4,
    "lat": 9,
    "lon": 47,
    "rad": 50,
    "desc": "exp_wayp1",
}

WAYPOINT_ENTITY_NAMES = [
    "zone.greg_phone_exp_wayp1",
    "zone.greg_phone_exp_wayp2",
    "zone.ram_phone_exp_wayp1",
    "zone.ram_phone_exp_wayp2",
]

LWT_MESSAGE = {"_type": "lwt", "tst": 1}

BAD_MESSAGE = {"_type": "unsupported", "tst": 1}

BAD_JSON_PREFIX = "--$this is bad json#--"
BAD_JSON_SUFFIX = "** and it ends here ^^"

# pylint: disable=len-as-condition


@pytest.fixture
def setup_comp(hass, mock_device_tracker_conf, mqtt_mock):
    """Initialize components."""
    hass.loop.run_until_complete(async_setup_component(hass, "device_tracker", {}))

    hass.states.async_set("zone.inner", "zoning", INNER_ZONE)

    hass.states.async_set("zone.inner_2", "zoning", INNER_ZONE)

    hass.states.async_set("zone.outer", "zoning", OUTER_ZONE)


async def setup_owntracks(hass, config, ctx_cls=owntracks.OwnTracksContext):
    """Set up OwnTracks."""
    MockConfigEntry(
        domain="owntracks", data={"webhook_id": "owntracks_test", "secret": "abcd"}
    ).add_to_hass(hass)

    with patch.object(owntracks, "OwnTracksContext", ctx_cls):
        assert await async_setup_component(hass, "owntracks", {"owntracks": config})
        await hass.async_block_till_done()


@pytest.fixture
def context(hass, setup_comp):
    """Set up the mocked context."""
    orig_context = owntracks.OwnTracksContext
    context = None

    def store_context(*args):
        """Store the context."""
        nonlocal context
        context = orig_context(*args)
        return context

    hass.loop.run_until_complete(
        setup_owntracks(
            hass,
            {
                CONF_MAX_GPS_ACCURACY: 200,
                CONF_WAYPOINT_IMPORT: True,
                CONF_WAYPOINT_WHITELIST: ["jon", "greg"],
            },
            store_context,
        )
    )

    def get_context():
        """Get the current context."""
        return context

    return get_context


async def send_message(hass, topic, message, corrupt=False):
    """Test the sending of a message."""
    str_message = json.dumps(message)
    if corrupt:
        mod_message = BAD_JSON_PREFIX + str_message + BAD_JSON_SUFFIX
    else:
        mod_message = str_message
    async_fire_mqtt_message(hass, topic, mod_message)
    await hass.async_block_till_done()
    await hass.async_block_till_done()


def assert_location_state(hass, location):
    """Test the assertion of a location state."""
    state = hass.states.get(DEVICE_TRACKER_STATE)
    assert state.state == location


def assert_location_latitude(hass, latitude):
    """Test the assertion of a location latitude."""
    state = hass.states.get(DEVICE_TRACKER_STATE)
    assert state.attributes.get("latitude") == latitude


def assert_location_longitude(hass, longitude):
    """Test the assertion of a location longitude."""
    state = hass.states.get(DEVICE_TRACKER_STATE)
    assert state.attributes.get("longitude") == longitude


def assert_location_accuracy(hass, accuracy):
    """Test the assertion of a location accuracy."""
    state = hass.states.get(DEVICE_TRACKER_STATE)
    assert state.attributes.get("gps_accuracy") == accuracy


def assert_location_source_type(hass, source_type):
    """Test the assertion of source_type."""
    state = hass.states.get(DEVICE_TRACKER_STATE)
    assert state.attributes.get("source_type") == source_type


def assert_mobile_tracker_state(hass, location, beacon=IBEACON_DEVICE):
    """Test the assertion of a mobile beacon tracker state."""
    dev_id = MOBILE_BEACON_FMT.format(beacon)
    state = hass.states.get(dev_id)
    assert state.state == location


def assert_mobile_tracker_latitude(hass, latitude, beacon=IBEACON_DEVICE):
    """Test the assertion of a mobile beacon tracker latitude."""
    dev_id = MOBILE_BEACON_FMT.format(beacon)
    state = hass.states.get(dev_id)
    assert state.attributes.get("latitude") == latitude


def assert_mobile_tracker_accuracy(hass, accuracy, beacon=IBEACON_DEVICE):
    """Test the assertion of a mobile beacon tracker accuracy."""
    dev_id = MOBILE_BEACON_FMT.format(beacon)
    state = hass.states.get(dev_id)
    assert state.attributes.get("gps_accuracy") == accuracy


async def test_location_invalid_devid(hass: HomeAssistant, context) -> None:
    """Test the update of a location."""
    await send_message(hass, "owntracks/paulus/nexus-5x", LOCATION_MESSAGE)
    state = hass.states.get("device_tracker.paulus_nexus_5x")
    assert state.state == "outer"


async def test_location_update(hass: HomeAssistant, context) -> None:
    """Test the update of a location."""
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    assert_location_source_type(hass, "gps")
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])
    assert_location_accuracy(hass, LOCATION_MESSAGE["acc"])
    assert_location_state(hass, "outer")


async def test_location_update_no_t_key(hass: HomeAssistant, context) -> None:
    """Test the update of a location when message does not contain 't'."""
    message = LOCATION_MESSAGE.copy()
    message.pop("t")
    await send_message(hass, LOCATION_TOPIC, message)

    assert_location_source_type(hass, "gps")
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])
    assert_location_accuracy(hass, LOCATION_MESSAGE["acc"])
    assert_location_state(hass, "outer")


async def test_location_inaccurate_gps(hass: HomeAssistant, context) -> None:
    """Test the location for inaccurate GPS information."""
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE_INACCURATE)

    # Ignored inaccurate GPS. Location remains at previous.
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])
    assert_location_longitude(hass, LOCATION_MESSAGE["lon"])


async def test_location_zero_accuracy_gps(hass: HomeAssistant, context) -> None:
    """Ignore the location for zero accuracy GPS information."""
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE_ZERO_ACCURACY)

    # Ignored inaccurate GPS. Location remains at previous.
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])
    assert_location_longitude(hass, LOCATION_MESSAGE["lon"])


# ------------------------------------------------------------------------
# GPS based event entry / exit testing
async def test_event_gps_entry_exit(hass: HomeAssistant, context) -> None:
    """Test the entry event."""
    # Entering the owntracks circular region named "inner"
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)

    # Enter uses the zone's gps co-ords
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")

    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    #  Updates ignored when in a zone
    #  note that LOCATION_MESSAGE is actually pretty far
    #  from INNER_ZONE and has good accuracy. I haven't
    #  received a transition message though so I'm still
    #  associated with the inner zone regardless of GPS.
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")

    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)

    # Exit switches back to GPS
    assert_location_latitude(hass, REGION_GPS_LEAVE_MESSAGE["lat"])
    assert_location_accuracy(hass, REGION_GPS_LEAVE_MESSAGE["acc"])
    assert_location_state(hass, "outer")

    # Left clean zone state
    assert not context().regions_entered[USER]

    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    # Now sending a location update moves me again.
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])
    assert_location_accuracy(hass, LOCATION_MESSAGE["acc"])


async def test_event_gps_with_spaces(hass: HomeAssistant, context) -> None:
    """Test the entry event."""
    message = build_message({"desc": "inner 2"}, REGION_GPS_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner 2")

    message = build_message({"desc": "inner 2"}, REGION_GPS_LEAVE_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)

    # Left clean zone state
    assert not context().regions_entered[USER]


async def test_event_gps_entry_inaccurate(hass: HomeAssistant, context) -> None:
    """Test the event for inaccurate entry."""
    # Set location to the outer zone.
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE_INACCURATE)

    # I enter the zone even though the message GPS was inaccurate.
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")


async def test_event_gps_entry_exit_inaccurate(hass: HomeAssistant, context) -> None:
    """Test the event for inaccurate exit."""
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)

    # Enter uses the zone's gps co-ords
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")

    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_INACCURATE)

    # Exit doesn't use inaccurate gps
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")

    # But does exit region correctly
    assert not context().regions_entered[USER]


async def test_event_gps_entry_exit_zero_accuracy(hass: HomeAssistant, context) -> None:
    """Test entry/exit events with accuracy zero."""
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE_ZERO)

    # Enter uses the zone's gps co-ords
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")

    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_ZERO)

    # Exit doesn't use zero gps
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")

    # But does exit region correctly
    assert not context().regions_entered[USER]


async def test_event_gps_exit_outside_zone_sets_away(
    hass: HomeAssistant, context
) -> None:
    """Test the event for exit zone."""
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
    assert_location_state(hass, "inner")

    # Exit message far away GPS location
    message = build_message({"lon": 90.0, "lat": 90.0}, REGION_GPS_LEAVE_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)

    # Exit forces zone change to away
    assert_location_state(hass, STATE_NOT_HOME)


async def test_event_gps_entry_exit_right_order(hass: HomeAssistant, context) -> None:
    """Test the event for ordering."""
    # Enter inner zone
    # Set location to the outer zone.
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
    assert_location_state(hass, "inner")

    # Enter inner2 zone
    message = build_message({"desc": "inner_2"}, REGION_GPS_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner_2")

    # Exit inner_2 - should be in 'inner'
    message = build_message({"desc": "inner_2"}, REGION_GPS_LEAVE_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner")

    # Exit inner - should be in 'outer'
    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
    assert_location_latitude(hass, REGION_GPS_LEAVE_MESSAGE["lat"])
    assert_location_accuracy(hass, REGION_GPS_LEAVE_MESSAGE["acc"])
    assert_location_state(hass, "outer")


async def test_event_gps_entry_exit_wrong_order(hass: HomeAssistant, context) -> None:
    """Test the event for wrong order."""
    # Enter inner zone
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
    assert_location_state(hass, "inner")

    # Enter inner2 zone
    message = build_message({"desc": "inner_2"}, REGION_GPS_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner_2")

    # Exit inner - should still be in 'inner_2'
    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
    assert_location_state(hass, "inner_2")

    # Exit inner_2 - should be in 'outer'
    message = build_message({"desc": "inner_2"}, REGION_GPS_LEAVE_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_latitude(hass, REGION_GPS_LEAVE_MESSAGE["lat"])
    assert_location_accuracy(hass, REGION_GPS_LEAVE_MESSAGE["acc"])
    assert_location_state(hass, "outer")


async def test_event_gps_entry_unknown_zone(hass: HomeAssistant, context) -> None:
    """Test the event for unknown zone."""
    # Just treat as location update
    message = build_message({"desc": "unknown"}, REGION_GPS_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_latitude(hass, REGION_GPS_ENTER_MESSAGE["lat"])
    assert_location_state(hass, "inner")


async def test_event_gps_exit_unknown_zone(hass: HomeAssistant, context) -> None:
    """Test the event for unknown zone."""
    # Just treat as location update
    message = build_message({"desc": "unknown"}, REGION_GPS_LEAVE_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_latitude(hass, REGION_GPS_LEAVE_MESSAGE["lat"])
    assert_location_state(hass, "outer")


async def test_event_entry_zone_loading_dash(hass: HomeAssistant, context) -> None:
    """Test the event for zone landing."""
    # Make sure the leading - is ignored
    # Owntracks uses this to switch on hold
    message = build_message({"desc": "-inner"}, REGION_GPS_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner")


async def test_events_only_on(hass: HomeAssistant, context) -> None:
    """Test events_only config suppresses location updates."""
    # Sending a location message that is not home
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)
    assert_location_state(hass, STATE_NOT_HOME)

    context().events_only = True

    # Enter and Leave messages
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE_OUTER)
    assert_location_state(hass, "outer")
    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_OUTER)
    assert_location_state(hass, STATE_NOT_HOME)

    # Sending a location message that is inside outer zone
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    # Ignored location update. Location remains at previous.
    assert_location_state(hass, STATE_NOT_HOME)


async def test_events_only_off(hass: HomeAssistant, context) -> None:
    """Test when events_only is False."""
    # Sending a location message that is not home
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)
    assert_location_state(hass, STATE_NOT_HOME)

    context().events_only = False

    # Enter and Leave messages
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE_OUTER)
    assert_location_state(hass, "outer")
    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_OUTER)
    assert_location_state(hass, STATE_NOT_HOME)

    # Sending a location message that is inside outer zone
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    # Location update processed
    assert_location_state(hass, "outer")


async def test_event_source_type_entry_exit(hass: HomeAssistant, context) -> None:
    """Test the entry and exit events of source type."""
    # Entering the owntracks circular region named "inner"
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)

    # source_type should be gps when entering using gps.
    assert_location_source_type(hass, "gps")

    # owntracks shouldn't send beacon events with acc = 0
    await send_message(
        hass, EVENT_TOPIC, build_message({"acc": 1}, REGION_BEACON_ENTER_MESSAGE)
    )

    # We should be able to enter a beacon zone even inside a gps zone
    assert_location_source_type(hass, "bluetooth_le")

    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)

    # source_type should be gps when leaving using gps.
    assert_location_source_type(hass, "gps")

    # owntracks shouldn't send beacon events with acc = 0
    await send_message(
        hass, EVENT_TOPIC, build_message({"acc": 1}, REGION_BEACON_LEAVE_MESSAGE)
    )

    assert_location_source_type(hass, "bluetooth_le")


# Region Beacon based event entry / exit testing
async def test_event_region_entry_exit(hass: HomeAssistant, context) -> None:
    """Test the entry event."""
    # Seeing a beacon named "inner"
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)

    # Enter uses the zone's gps co-ords
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")

    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    #  Updates ignored when in a zone
    #  note that LOCATION_MESSAGE is actually pretty far
    #  from INNER_ZONE and has good accuracy. I haven't
    #  received a transition message though so I'm still
    #  associated with the inner zone regardless of GPS.
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")

    await send_message(hass, EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)

    # Exit switches back to GPS but the beacon has no coords
    # so I am still located at the center of the inner region
    # until I receive a location update.
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")

    # Left clean zone state
    assert not context().regions_entered[USER]

    # Now sending a location update moves me again.
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])
    assert_location_accuracy(hass, LOCATION_MESSAGE["acc"])


async def test_event_region_with_spaces(hass: HomeAssistant, context) -> None:
    """Test the entry event."""
    message = build_message({"desc": "inner 2"}, REGION_BEACON_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner 2")

    message = build_message({"desc": "inner 2"}, REGION_BEACON_LEAVE_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)

    # Left clean zone state
    assert not context().regions_entered[USER]


async def test_event_region_entry_exit_right_order(
    hass: HomeAssistant, context
) -> None:
    """Test the event for ordering."""
    # Enter inner zone
    # Set location to the outer zone.
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    # See 'inner' region beacon
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
    assert_location_state(hass, "inner")

    # See 'inner_2' region beacon
    message = build_message({"desc": "inner_2"}, REGION_BEACON_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner_2")

    # Exit inner_2 - should be in 'inner'
    message = build_message({"desc": "inner_2"}, REGION_BEACON_LEAVE_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner")

    # Exit inner - should be in 'outer'
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)

    # I have not had an actual location update yet and my
    # coordinates are set to the center of the last region I
    # entered which puts me in the inner zone.
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner")


async def test_event_region_entry_exit_wrong_order(
    hass: HomeAssistant, context
) -> None:
    """Test the event for wrong order."""
    # Enter inner zone
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
    assert_location_state(hass, "inner")

    # Enter inner2 zone
    message = build_message({"desc": "inner_2"}, REGION_BEACON_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner_2")

    # Exit inner - should still be in 'inner_2'
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)
    assert_location_state(hass, "inner_2")

    # Exit inner_2 - should be in 'outer'
    message = build_message({"desc": "inner_2"}, REGION_BEACON_LEAVE_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)

    # I have not had an actual location update yet and my
    # coordinates are set to the center of the last region I
    # entered which puts me in the inner_2 zone.
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_accuracy(hass, INNER_ZONE["radius"])
    assert_location_state(hass, "inner_2")


async def test_event_beacon_unknown_zone_no_location(
    hass: HomeAssistant, context
) -> None:
    """Test the event for unknown zone."""
    # A beacon which does not match a HA zone is the
    # definition of a mobile beacon. In this case, "unknown"
    # will be turned into device_tracker.beacon_unknown and
    # that will be tracked at my current location. Except
    # in this case my Device hasn't had a location message
    # yet so it's in an odd state where it has state.state
    # None and no GPS coords to set the beacon to.
    hass.states.async_set(DEVICE_TRACKER_STATE, None)

    message = build_message({"desc": "unknown"}, REGION_BEACON_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)

    # My current state is None because I haven't seen a
    # location message or a GPS or Region # Beacon event
    # message. None is the state the test harness set for
    # the Device during test case setup.
    assert_location_state(hass, "None")

    # We have had no location yet, so the beacon status
    # set to unknown.
    assert_mobile_tracker_state(hass, "unknown", "unknown")


async def test_event_beacon_unknown_zone(hass: HomeAssistant, context) -> None:
    """Test the event for unknown zone."""
    # A beacon which does not match a HA zone is the
    # definition of a mobile beacon. In this case, "unknown"
    # will be turned into device_tracker.beacon_unknown and
    # that will be tracked at my current location. First I
    # set my location so that my state is 'outer'

    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)
    assert_location_state(hass, "outer")

    message = build_message({"desc": "unknown"}, REGION_BEACON_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)

    # My state is still outer and now the unknown beacon
    # has joined me at outer.
    assert_location_state(hass, "outer")
    assert_mobile_tracker_state(hass, "outer", "unknown")


async def test_event_beacon_entry_zone_loading_dash(
    hass: HomeAssistant, context
) -> None:
    """Test the event for beacon zone landing."""
    # Make sure the leading - is ignored
    # Owntracks uses this to switch on hold

    message = build_message({"desc": "-inner"}, REGION_BEACON_ENTER_MESSAGE)
    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner")


# ------------------------------------------------------------------------
# Mobile Beacon based event entry / exit testing
async def test_mobile_enter_move_beacon(hass: HomeAssistant, context) -> None:
    """Test the movement of a beacon."""
    # I am in the outer zone.
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    # I see the 'keys' beacon. I set the location of the
    # beacon_keys tracker to my current device location.
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)

    assert_mobile_tracker_latitude(hass, LOCATION_MESSAGE["lat"])
    assert_mobile_tracker_state(hass, "outer")

    # Location update to outside of defined zones.
    # I am now 'not home' and neither are my keys.
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)

    assert_location_state(hass, STATE_NOT_HOME)
    assert_mobile_tracker_state(hass, STATE_NOT_HOME)

    not_home_lat = LOCATION_MESSAGE_NOT_HOME["lat"]
    assert_location_latitude(hass, not_home_lat)
    assert_mobile_tracker_latitude(hass, not_home_lat)


async def test_mobile_enter_exit_region_beacon(hass: HomeAssistant, context) -> None:
    """Test the enter and the exit of a mobile beacon."""
    # I am in the outer zone.
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    # I see a new mobile beacon
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
    assert_mobile_tracker_latitude(hass, OUTER_ZONE["latitude"])
    assert_mobile_tracker_state(hass, "outer")

    # GPS enter message should move beacon
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)

    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])
    assert_mobile_tracker_state(hass, REGION_GPS_ENTER_MESSAGE["desc"])

    # Exit inner zone to outer zone should move beacon to
    # center of outer zone
    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
    assert_mobile_tracker_latitude(hass, REGION_GPS_LEAVE_MESSAGE["lat"])
    assert_mobile_tracker_state(hass, "outer")


async def test_mobile_exit_move_beacon(hass: HomeAssistant, context) -> None:
    """Test the exit move of a beacon."""
    # I am in the outer zone.
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)

    # I see a new mobile beacon
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
    assert_mobile_tracker_latitude(hass, OUTER_ZONE["latitude"])
    assert_mobile_tracker_state(hass, "outer")

    # Exit mobile beacon, should set location
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)

    assert_mobile_tracker_latitude(hass, OUTER_ZONE["latitude"])
    assert_mobile_tracker_state(hass, "outer")

    # Move after exit should do nothing
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)
    assert_mobile_tracker_latitude(hass, OUTER_ZONE["latitude"])
    assert_mobile_tracker_state(hass, "outer")


async def test_mobile_multiple_async_enter_exit(hass: HomeAssistant, context) -> None:
    """Test the multiple entering."""
    # Test race condition
    for _ in range(0, 20):
        async_fire_mqtt_message(
            hass, EVENT_TOPIC, json.dumps(MOBILE_BEACON_ENTER_EVENT_MESSAGE)
        )
        async_fire_mqtt_message(
            hass, EVENT_TOPIC, json.dumps(MOBILE_BEACON_LEAVE_EVENT_MESSAGE)
        )

    async_fire_mqtt_message(
        hass, EVENT_TOPIC, json.dumps(MOBILE_BEACON_ENTER_EVENT_MESSAGE)
    )

    await hass.async_block_till_done()
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)
    assert len(context().mobile_beacons_active["greg_phone"]) == 0


async def test_mobile_multiple_enter_exit(hass: HomeAssistant, context) -> None:
    """Test the multiple entering."""
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)

    assert len(context().mobile_beacons_active["greg_phone"]) == 0


async def test_complex_movement(hass: HomeAssistant, context) -> None:
    """Test a complex sequence representative of real-world use."""
    # I am in the outer zone.
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)
    assert_location_state(hass, "outer")

    # gps to inner location and event, as actually happens with OwnTracks
    location_message = build_message(
        {
            "lat": REGION_GPS_ENTER_MESSAGE["lat"],
            "lon": REGION_GPS_ENTER_MESSAGE["lon"],
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, LOCATION_TOPIC, location_message)
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_state(hass, "inner")

    # region beacon enter inner event and location as actually happens
    # with OwnTracks
    location_message = build_message(
        {
            "lat": location_message["lat"] + FIVE_M,
            "lon": location_message["lon"] + FIVE_M,
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_state(hass, "inner")

    # see keys mobile beacon and location message as actually happens
    location_message = build_message(
        {
            "lat": location_message["lat"] + FIVE_M,
            "lon": location_message["lon"] + FIVE_M,
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])
    assert_location_state(hass, "inner")
    assert_mobile_tracker_state(hass, "inner")

    # Slightly odd, I leave the location by gps before I lose
    # sight of the region beacon. This is also a little odd in
    # that my GPS coords are now in the 'outer' zone but I did not
    # "enter" that zone when I started up so my location is not
    # the center of OUTER_ZONE, but rather just my GPS location.

    # gps out of inner event and location
    location_message = build_message(
        {
            "lat": REGION_GPS_LEAVE_MESSAGE["lat"],
            "lon": REGION_GPS_LEAVE_MESSAGE["lon"],
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_latitude(hass, REGION_GPS_LEAVE_MESSAGE["lat"])
    assert_mobile_tracker_latitude(hass, REGION_GPS_LEAVE_MESSAGE["lat"])
    assert_location_state(hass, "outer")
    assert_mobile_tracker_state(hass, "outer")

    # region beacon leave inner
    location_message = build_message(
        {
            "lat": location_message["lat"] - FIVE_M,
            "lon": location_message["lon"] - FIVE_M,
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_latitude(hass, location_message["lat"])
    assert_mobile_tracker_latitude(hass, location_message["lat"])
    assert_location_state(hass, "outer")
    assert_mobile_tracker_state(hass, "outer")

    # lose keys mobile beacon
    lost_keys_location_message = build_message(
        {
            "lat": location_message["lat"] - FIVE_M,
            "lon": location_message["lon"] - FIVE_M,
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, LOCATION_TOPIC, lost_keys_location_message)
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)
    assert_location_latitude(hass, lost_keys_location_message["lat"])
    assert_mobile_tracker_latitude(hass, lost_keys_location_message["lat"])
    assert_location_state(hass, "outer")
    assert_mobile_tracker_state(hass, "outer")

    # gps leave outer
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE_NOT_HOME)
    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE_OUTER)
    assert_location_latitude(hass, LOCATION_MESSAGE_NOT_HOME["lat"])
    assert_mobile_tracker_latitude(hass, lost_keys_location_message["lat"])
    assert_location_state(hass, "not_home")
    assert_mobile_tracker_state(hass, "outer")

    # location move not home
    location_message = build_message(
        {
            "lat": LOCATION_MESSAGE_NOT_HOME["lat"] - FIVE_M,
            "lon": LOCATION_MESSAGE_NOT_HOME["lon"] - FIVE_M,
        },
        LOCATION_MESSAGE_NOT_HOME,
    )
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_latitude(hass, location_message["lat"])
    assert_mobile_tracker_latitude(hass, lost_keys_location_message["lat"])
    assert_location_state(hass, "not_home")
    assert_mobile_tracker_state(hass, "outer")


async def test_complex_movement_sticky_keys_beacon(
    hass: HomeAssistant, context
) -> None:
    """Test a complex sequence which was previously broken."""
    # I am not_home
    await send_message(hass, LOCATION_TOPIC, LOCATION_MESSAGE)
    assert_location_state(hass, "outer")

    # gps to inner location and event, as actually happens with OwnTracks
    location_message = build_message(
        {
            "lat": REGION_GPS_ENTER_MESSAGE["lat"],
            "lon": REGION_GPS_ENTER_MESSAGE["lon"],
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, LOCATION_TOPIC, location_message)
    await send_message(hass, EVENT_TOPIC, REGION_GPS_ENTER_MESSAGE)
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_state(hass, "inner")

    # see keys mobile beacon and location message as actually happens
    location_message = build_message(
        {
            "lat": location_message["lat"] + FIVE_M,
            "lon": location_message["lon"] + FIVE_M,
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])
    assert_location_state(hass, "inner")
    assert_mobile_tracker_state(hass, "inner")

    # region beacon enter inner event and location as actually happens
    # with OwnTracks
    location_message = build_message(
        {
            "lat": location_message["lat"] + FIVE_M,
            "lon": location_message["lon"] + FIVE_M,
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_state(hass, "inner")

    # This sequence of moves would cause keys to follow
    # greg_phone around even after the OwnTracks sent
    # a mobile beacon 'leave' event for the keys.
    # leave keys
    await send_message(hass, LOCATION_TOPIC, location_message)
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_state(hass, "inner")
    assert_mobile_tracker_state(hass, "inner")
    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])

    # leave inner region beacon
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_state(hass, "inner")
    assert_mobile_tracker_state(hass, "inner")
    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])

    # enter inner region beacon
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_ENTER_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_latitude(hass, INNER_ZONE["latitude"])
    assert_location_state(hass, "inner")
    assert_mobile_tracker_state(hass, "inner")
    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])

    # enter keys
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_ENTER_EVENT_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_state(hass, "inner")
    assert_mobile_tracker_state(hass, "inner")
    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])

    # leave keys
    await send_message(hass, LOCATION_TOPIC, location_message)
    await send_message(hass, EVENT_TOPIC, MOBILE_BEACON_LEAVE_EVENT_MESSAGE)
    assert_location_state(hass, "inner")
    assert_mobile_tracker_state(hass, "inner")
    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])

    # leave inner region beacon
    await send_message(hass, EVENT_TOPIC, REGION_BEACON_LEAVE_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, location_message)
    assert_location_state(hass, "inner")
    assert_mobile_tracker_state(hass, "inner")
    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])

    # GPS leave inner region, I'm in the 'outer' region now
    # but on GPS coords
    leave_location_message = build_message(
        {
            "lat": REGION_GPS_LEAVE_MESSAGE["lat"],
            "lon": REGION_GPS_LEAVE_MESSAGE["lon"],
        },
        LOCATION_MESSAGE,
    )
    await send_message(hass, EVENT_TOPIC, REGION_GPS_LEAVE_MESSAGE)
    await send_message(hass, LOCATION_TOPIC, leave_location_message)
    assert_location_state(hass, "outer")
    assert_mobile_tracker_state(hass, "inner")
    assert_location_latitude(hass, REGION_GPS_LEAVE_MESSAGE["lat"])
    assert_mobile_tracker_latitude(hass, INNER_ZONE["latitude"])


async def test_waypoint_import_simple(hass: HomeAssistant, context) -> None:
    """Test a simple import of list of waypoints."""
    waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
    await send_message(hass, WAYPOINTS_TOPIC, waypoints_message)
    # Check if it made it into states
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[0])
    assert wayp is not None
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[1])
    assert wayp is not None


async def test_waypoint_import_block(hass: HomeAssistant, context) -> None:
    """Test import of list of waypoints for blocked user."""
    waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
    await send_message(hass, WAYPOINTS_TOPIC_BLOCKED, waypoints_message)
    # Check if it made it into states
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[2])
    assert wayp is None
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[3])
    assert wayp is None


async def test_waypoint_import_no_whitelist(hass: HomeAssistant, setup_comp) -> None:
    """Test import of list of waypoints with no whitelist set."""
    await setup_owntracks(
        hass,
        {
            CONF_MAX_GPS_ACCURACY: 200,
            CONF_WAYPOINT_IMPORT: True,
            CONF_MQTT_TOPIC: "owntracks/#",
        },
    )

    waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
    await send_message(hass, WAYPOINTS_TOPIC_BLOCKED, waypoints_message)
    # Check if it made it into states
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[2])
    assert wayp is not None
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[3])
    assert wayp is not None


async def test_waypoint_import_bad_json(hass: HomeAssistant, context) -> None:
    """Test importing a bad JSON payload."""
    waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
    await send_message(hass, WAYPOINTS_TOPIC, waypoints_message, True)
    # Check if it made it into states
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[2])
    assert wayp is None
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[3])
    assert wayp is None


async def test_waypoint_import_existing(hass: HomeAssistant, context) -> None:
    """Test importing a zone that exists."""
    waypoints_message = WAYPOINTS_EXPORTED_MESSAGE.copy()
    await send_message(hass, WAYPOINTS_TOPIC, waypoints_message)
    # Get the first waypoint exported
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[0])
    # Send an update
    waypoints_message = WAYPOINTS_UPDATED_MESSAGE.copy()
    await send_message(hass, WAYPOINTS_TOPIC, waypoints_message)
    new_wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[0])
    assert wayp == new_wayp


async def test_single_waypoint_import(hass: HomeAssistant, context) -> None:
    """Test single waypoint message."""
    waypoint_message = WAYPOINT_MESSAGE.copy()
    await send_message(hass, WAYPOINT_TOPIC, waypoint_message)
    wayp = hass.states.get(WAYPOINT_ENTITY_NAMES[0])
    assert wayp is not None


async def test_not_implemented_message(hass: HomeAssistant, context) -> None:
    """Handle not implemented message type."""
    patch_handler = patch(
        "homeassistant.components.owntracks.messages.async_handle_not_impl_msg",
        return_value=False,
    )
    patch_handler.start()
    assert not await send_message(hass, LWT_TOPIC, LWT_MESSAGE)
    patch_handler.stop()


async def test_unsupported_message(hass: HomeAssistant, context) -> None:
    """Handle not implemented message type."""
    patch_handler = patch(
        "homeassistant.components.owntracks.messages.async_handle_unsupported_msg",
        return_value=False,
    )
    patch_handler.start()
    assert not await send_message(hass, BAD_TOPIC, BAD_MESSAGE)
    patch_handler.stop()


def generate_ciphers(secret):
    """Generate test ciphers for the DEFAULT_LOCATION_MESSAGE."""
    # PyNaCl ciphertext generation will fail if the module
    # cannot be imported. However, the test for decryption
    # also relies on this library and won't be run without it.
    import base64
    import pickle

    try:
        from nacl.encoding import Base64Encoder
        from nacl.secret import SecretBox

        keylen = SecretBox.KEY_SIZE
        key = secret.encode("utf-8")
        key = key[:keylen]
        key = key.ljust(keylen, b"\0")

        msg = json.dumps(DEFAULT_LOCATION_MESSAGE).encode("utf-8")

        ctxt = SecretBox(key).encrypt(msg, encoder=Base64Encoder).decode("utf-8")
    except (ImportError, OSError):
        ctxt = ""

    mctxt = base64.b64encode(
        pickle.dumps(
            (
                secret.encode("utf-8"),
                json.dumps(DEFAULT_LOCATION_MESSAGE).encode("utf-8"),
            )
        )
    ).decode("utf-8")
    return ctxt, mctxt


TEST_SECRET_KEY = "s3cretkey"

CIPHERTEXT, MOCK_CIPHERTEXT = generate_ciphers(TEST_SECRET_KEY)

ENCRYPTED_LOCATION_MESSAGE = {
    # Encrypted version of LOCATION_MESSAGE using libsodium and TEST_SECRET_KEY
    "_type": "encrypted",
    "data": CIPHERTEXT,
}

MOCK_ENCRYPTED_LOCATION_MESSAGE = {
    # Mock-encrypted version of LOCATION_MESSAGE using pickle
    "_type": "encrypted",
    "data": MOCK_CIPHERTEXT,
}


def mock_cipher():
    """Return a dummy pickle-based cipher."""

    def mock_decrypt(ciphertext, key):
        """Decrypt/unpickle."""
        import base64
        import pickle

        (mkey, plaintext) = pickle.loads(base64.b64decode(ciphertext))
        if key != mkey:
            raise ValueError()
        return plaintext

    return len(TEST_SECRET_KEY), mock_decrypt


@pytest.fixture
def config_context(hass, setup_comp):
    """Set up the mocked context."""
    patch_load = patch(
        "homeassistant.components.device_tracker.async_load_config",
        return_value=[],
    )
    patch_load.start()

    patch_save = patch(
        "homeassistant.components.device_tracker.DeviceTracker.async_update_config"
    )
    patch_save.start()

    yield

    patch_load.stop()
    patch_save.stop()


@pytest.fixture(name="not_supports_encryption")
def mock_not_supports_encryption():
    """Mock non successful nacl import."""
    with patch(
        "homeassistant.components.owntracks.messages.supports_encryption",
        return_value=False,
    ):
        yield


@pytest.fixture(name="get_cipher_error")
def mock_get_cipher_error():
    """Mock non successful cipher."""
    with patch(
        "homeassistant.components.owntracks.messages.get_cipher", side_effect=OSError()
    ):
        yield


@patch("homeassistant.components.owntracks.messages.get_cipher", mock_cipher)
async def test_encrypted_payload(hass: HomeAssistant, setup_comp) -> None:
    """Test encrypted payload."""
    await setup_owntracks(hass, {CONF_SECRET: TEST_SECRET_KEY})
    await send_message(hass, LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])


@patch("homeassistant.components.owntracks.messages.get_cipher", mock_cipher)
async def test_encrypted_payload_topic_key(hass: HomeAssistant, setup_comp) -> None:
    """Test encrypted payload with a topic key."""
    await setup_owntracks(hass, {CONF_SECRET: {LOCATION_TOPIC: TEST_SECRET_KEY}})
    await send_message(hass, LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])


async def test_encrypted_payload_not_supports_encryption(
    hass: HomeAssistant, setup_comp, not_supports_encryption
) -> None:
    """Test encrypted payload with no supported encryption."""
    await setup_owntracks(hass, {CONF_SECRET: TEST_SECRET_KEY})
    await send_message(hass, LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
    assert hass.states.get(DEVICE_TRACKER_STATE) is None


async def test_encrypted_payload_get_cipher_error(
    hass: HomeAssistant, setup_comp, get_cipher_error
) -> None:
    """Test encrypted payload with no supported encryption."""
    await setup_owntracks(hass, {CONF_SECRET: TEST_SECRET_KEY})
    await send_message(hass, LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
    assert hass.states.get(DEVICE_TRACKER_STATE) is None


@patch("homeassistant.components.owntracks.messages.get_cipher", mock_cipher)
async def test_encrypted_payload_no_key(hass: HomeAssistant, setup_comp) -> None:
    """Test encrypted payload with no key, ."""
    assert hass.states.get(DEVICE_TRACKER_STATE) is None
    await setup_owntracks(hass, {CONF_SECRET: {}})
    await send_message(hass, LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
    assert hass.states.get(DEVICE_TRACKER_STATE) is None


@patch("homeassistant.components.owntracks.messages.get_cipher", mock_cipher)
async def test_encrypted_payload_wrong_key(hass: HomeAssistant, setup_comp) -> None:
    """Test encrypted payload with wrong key."""
    await setup_owntracks(hass, {CONF_SECRET: "wrong key"})
    await send_message(hass, LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
    assert hass.states.get(DEVICE_TRACKER_STATE) is None


@patch("homeassistant.components.owntracks.messages.get_cipher", mock_cipher)
async def test_encrypted_payload_wrong_topic_key(
    hass: HomeAssistant, setup_comp
) -> None:
    """Test encrypted payload with wrong  topic key."""
    await setup_owntracks(hass, {CONF_SECRET: {LOCATION_TOPIC: "wrong key"}})
    await send_message(hass, LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
    assert hass.states.get(DEVICE_TRACKER_STATE) is None


@patch("homeassistant.components.owntracks.messages.get_cipher", mock_cipher)
async def test_encrypted_payload_no_topic_key(hass: HomeAssistant, setup_comp) -> None:
    """Test encrypted payload with no topic key."""
    await setup_owntracks(
        hass, {CONF_SECRET: {"owntracks/{}/{}".format(USER, "otherdevice"): "foobar"}}
    )
    await send_message(hass, LOCATION_TOPIC, MOCK_ENCRYPTED_LOCATION_MESSAGE)
    assert hass.states.get(DEVICE_TRACKER_STATE) is None


async def test_encrypted_payload_libsodium(hass: HomeAssistant, setup_comp) -> None:
    """Test sending encrypted message payload."""
    try:
        import nacl  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("PyNaCl/libsodium is not installed")
        return

    await setup_owntracks(hass, {CONF_SECRET: TEST_SECRET_KEY})

    await send_message(hass, LOCATION_TOPIC, ENCRYPTED_LOCATION_MESSAGE)
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])


async def test_customized_mqtt_topic(hass: HomeAssistant, setup_comp) -> None:
    """Test subscribing to a custom mqtt topic."""
    await setup_owntracks(hass, {CONF_MQTT_TOPIC: "mytracks/#"})

    topic = f"mytracks/{USER}/{DEVICE}"

    await send_message(hass, topic, LOCATION_MESSAGE)
    assert_location_latitude(hass, LOCATION_MESSAGE["lat"])


async def test_region_mapping(hass: HomeAssistant, setup_comp) -> None:
    """Test region to zone mapping."""
    await setup_owntracks(hass, {CONF_REGION_MAPPING: {"foo": "inner"}})

    hass.states.async_set("zone.inner", "zoning", INNER_ZONE)

    message = build_message({"desc": "foo"}, REGION_GPS_ENTER_MESSAGE)
    assert message["desc"] == "foo"

    await send_message(hass, EVENT_TOPIC, message)
    assert_location_state(hass, "inner")


async def test_restore_state(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that we can restore state."""
    entry = MockConfigEntry(
        domain="owntracks", data={"webhook_id": "owntracks_test", "secret": "abcd"}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post(
        "/api/webhook/owntracks_test",
        json=LOCATION_MESSAGE,
        headers={"X-Limit-u": "Paulus", "X-Limit-d": "Pixel"},
    )
    assert resp.status == 200
    await hass.async_block_till_done()

    state_1 = hass.states.get("device_tracker.paulus_pixel")
    assert state_1 is not None

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    state_2 = hass.states.get("device_tracker.paulus_pixel")
    assert state_2 is not None

    assert state_1 is not state_2

    assert state_1.state == state_2.state
    assert state_1.name == state_2.name
    assert state_1.attributes["latitude"] == state_2.attributes["latitude"]
    assert state_1.attributes["longitude"] == state_2.attributes["longitude"]
    assert state_1.attributes["battery_level"] == state_2.attributes["battery_level"]
    assert state_1.attributes["source_type"] == state_2.attributes["source_type"]


async def test_returns_empty_friends(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that an empty list of persons' locations is returned."""
    entry = MockConfigEntry(
        domain="owntracks", data={"webhook_id": "owntracks_test", "secret": "abcd"}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post(
        "/api/webhook/owntracks_test",
        json=LOCATION_MESSAGE,
        headers={"X-Limit-u": "Paulus", "X-Limit-d": "Pixel"},
    )

    assert resp.status == 200
    assert await resp.text() == "[]"


async def test_returns_array_friends(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that a list of persons' current locations is returned."""
    otracks = MockConfigEntry(
        domain="owntracks", data={"webhook_id": "owntracks_test", "secret": "abcd"}
    )
    otracks.add_to_hass(hass)

    await hass.config_entries.async_setup(otracks.entry_id)
    await hass.async_block_till_done()

    # Setup device_trackers
    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {
                    "name": "person 1",
                    "id": "person1",
                    "device_trackers": ["device_tracker.person_1_tracker_1"],
                },
                {
                    "name": "person2",
                    "id": "person2",
                    "device_trackers": ["device_tracker.person_2_tracker_1"],
                },
            ]
        },
    )
    hass.states.async_set(
        "device_tracker.person_1_tracker_1", "home", {"latitude": 10, "longitude": 20}
    )

    client = await hass_client()
    resp = await client.post(
        "/api/webhook/owntracks_test",
        json=LOCATION_MESSAGE,
        headers={"X-Limit-u": "Paulus", "X-Limit-d": "Pixel"},
    )

    assert resp.status == 200
    response_json = json.loads(await resp.text())

    assert response_json[0]["lat"] == 10
    assert response_json[0]["lon"] == 20
    assert response_json[0]["tid"] == "p1"
