"""
Support the OwnTracks platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.owntracks/
"""
import json
import logging
import threading
from collections import defaultdict

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.components.mqtt as mqtt
from homeassistant.const import STATE_HOME
from homeassistant.util import convert, slugify
from homeassistant.components import zone as zone_comp
from homeassistant.components.device_tracker import PLATFORM_SCHEMA

DEPENDENCIES = ['mqtt']

REGIONS_ENTERED = defaultdict(list)
MOBILE_BEACONS_ACTIVE = defaultdict(list)

BEACON_DEV_ID = 'beacon'

LOCATION_TOPIC = 'owntracks/+/+'
EVENT_TOPIC = 'owntracks/+/+/event'
WAYPOINT_TOPIC = 'owntracks/{}/{}/waypoint'

_LOGGER = logging.getLogger(__name__)

LOCK = threading.Lock()

CONF_MAX_GPS_ACCURACY = 'max_gps_accuracy'
CONF_WAYPOINT_IMPORT = 'waypoints'
CONF_WAYPOINT_WHITELIST = 'waypoint_whitelist'

VALIDATE_LOCATION = 'location'
VALIDATE_TRANSITION = 'transition'
VALIDATE_WAYPOINTS = 'waypoints'

WAYPOINT_LAT_KEY = 'lat'
WAYPOINT_LON_KEY = 'lon'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
    vol.Optional(CONF_WAYPOINT_IMPORT, default=True): cv.boolean,
    vol.Optional(CONF_WAYPOINT_WHITELIST): vol.All(cv.ensure_list, [cv.string])
})


def setup_scanner(hass, config, see):
    """Setup an OwnTracks tracker."""
    max_gps_accuracy = config.get(CONF_MAX_GPS_ACCURACY)
    waypoint_import = config.get(CONF_WAYPOINT_IMPORT)
    waypoint_whitelist = config.get(CONF_WAYPOINT_WHITELIST)

    def validate_payload(payload, data_type):
        """Validate OwnTracks payload."""
        try:
            data = json.loads(payload)
        except ValueError:
            # If invalid JSON
            _LOGGER.error('Unable to parse payload as JSON: %s', payload)
            return None
        if not isinstance(data, dict) or data.get('_type') != data_type:
            _LOGGER.debug('Skipping %s update for following data '
                          'because of missing or malformatted data: %s',
                          data_type, data)
            return None
        if data_type == VALIDATE_TRANSITION or data_type == VALIDATE_WAYPOINTS:
            return data
        if max_gps_accuracy is not None and \
                convert(data.get('acc'), float, 0.0) > max_gps_accuracy:
            _LOGGER.warning('Ignoring %s update because expected GPS '
                            'accuracy %s is not met: %s',
                            data_type, max_gps_accuracy, payload)
            return None
        if convert(data.get('acc'), float, 1.0) == 0.0:
            _LOGGER.warning('Ignoring %s update because GPS accuracy'
                            'is zero: %s',
                            data_type, payload)
            return None

        return data

    def owntracks_location_update(topic, payload, qos):
        """MQTT message received."""
        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typelocation
        data = validate_payload(payload, VALIDATE_LOCATION)
        if not data:
            return

        dev_id, kwargs = _parse_see_args(topic, data)

        # Block updates if we're in a region
        with LOCK:
            if REGIONS_ENTERED[dev_id]:
                _LOGGER.debug(
                    "location update ignored - inside region %s",
                    REGIONS_ENTERED[-1])
                return

            see(**kwargs)
            see_beacons(dev_id, kwargs)

    def owntracks_event_update(topic, payload, qos):
        """MQTT event (geofences) received."""
        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typetransition
        data = validate_payload(payload, VALIDATE_TRANSITION)
        if not data:
            return

        if data.get('desc') is None:
            _LOGGER.error(
                "Location missing from `Entering/Leaving` message - "
                "please turn `Share` on in OwnTracks app")
            return
        # OwnTracks uses - at the start of a beacon zone
        # to switch on 'hold mode' - ignore this
        location = slugify(data['desc'].lstrip("-"))
        if location.lower() == 'home':
            location = STATE_HOME

        dev_id, kwargs = _parse_see_args(topic, data)

        def enter_event():
            """Execute enter event."""
            zone = hass.states.get("zone.{}".format(location))
            with LOCK:
                if zone is None and data.get('t') == 'b':
                    # Not a HA zone, and a beacon so assume mobile
                    beacons = MOBILE_BEACONS_ACTIVE[dev_id]
                    if location not in beacons:
                        beacons.append(location)
                    _LOGGER.info("Added beacon %s", location)
                else:
                    # Normal region
                    regions = REGIONS_ENTERED[dev_id]
                    if location not in regions:
                        regions.append(location)
                    _LOGGER.info("Enter region %s", location)
                    _set_gps_from_zone(kwargs, location, zone)

                see(**kwargs)
                see_beacons(dev_id, kwargs)

        def leave_event():
            """Execute leave event."""
            with LOCK:
                regions = REGIONS_ENTERED[dev_id]
                if location in regions:
                    regions.remove(location)
                new_region = regions[-1] if regions else None

                if new_region:
                    # Exit to previous region
                    zone = hass.states.get("zone.{}".format(new_region))
                    _set_gps_from_zone(kwargs, new_region, zone)
                    _LOGGER.info("Exit to %s", new_region)
                    see(**kwargs)
                    see_beacons(dev_id, kwargs)

                else:
                    _LOGGER.info("Exit to GPS")
                    # Check for GPS accuracy
                    valid_gps = True
                    if 'acc' in data:
                        if data['acc'] == 0.0:
                            valid_gps = False
                            _LOGGER.warning(
                                'Ignoring GPS in region exit because accuracy'
                                'is zero: %s',
                                payload)
                        if (max_gps_accuracy is not None and
                                data['acc'] > max_gps_accuracy):
                            valid_gps = False
                            _LOGGER.warning(
                                'Ignoring GPS in region exit because expected '
                                'GPS accuracy %s is not met: %s',
                                max_gps_accuracy, payload)
                    if valid_gps:
                        see(**kwargs)
                        see_beacons(dev_id, kwargs)

                beacons = MOBILE_BEACONS_ACTIVE[dev_id]
                if location in beacons:
                    beacons.remove(location)
                    _LOGGER.info("Remove beacon %s", location)

        if data['event'] == 'enter':
            enter_event()
        elif data['event'] == 'leave':
            leave_event()
        else:
            _LOGGER.error(
                'Misformatted mqtt msgs, _type=transition, event=%s',
                data['event'])
            return

    def owntracks_waypoint_update(topic, payload, qos):
        """List of waypoints published by a user."""
        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typewaypoints
        data = validate_payload(payload, VALIDATE_WAYPOINTS)
        if not data:
            return

        wayps = data['waypoints']
        _LOGGER.info("Got %d waypoints from %s", len(wayps), topic)
        for wayp in wayps:
            name = wayp['desc']
            pretty_name = parse_topic(topic, True)[1] + ' - ' + name
            lat = wayp[WAYPOINT_LAT_KEY]
            lon = wayp[WAYPOINT_LON_KEY]
            rad = wayp['rad']

            # check zone exists
            entity_id = zone_comp.ENTITY_ID_FORMAT.format(slugify(pretty_name))

            # Check if state already exists
            if hass.states.get(entity_id) is not None:
                continue

            zone = zone_comp.Zone(hass, pretty_name, lat, lon, rad,
                                  zone_comp.ICON_IMPORT, False)
            zone.entity_id = entity_id
            zone.update_ha_state()

    def see_beacons(dev_id, kwargs_param):
        """Set active beacons to the current location."""
        kwargs = kwargs_param.copy()
        # the battery state applies to the tracking device, not the beacon
        kwargs.pop('battery', None)
        for beacon in MOBILE_BEACONS_ACTIVE[dev_id]:
            kwargs['dev_id'] = "{}_{}".format(BEACON_DEV_ID, beacon)
            kwargs['host_name'] = beacon
            see(**kwargs)

    mqtt.subscribe(hass, LOCATION_TOPIC, owntracks_location_update, 1)
    mqtt.subscribe(hass, EVENT_TOPIC, owntracks_event_update, 1)

    if waypoint_import:
        if waypoint_whitelist is None:
            mqtt.subscribe(hass, WAYPOINT_TOPIC.format('+', '+'),
                           owntracks_waypoint_update, 1)
        else:
            for whitelist_user in waypoint_whitelist:
                mqtt.subscribe(hass, WAYPOINT_TOPIC.format(whitelist_user,
                                                           '+'),
                               owntracks_waypoint_update, 1)

    return True


def parse_topic(topic, pretty=False):
    """Parse an MQTT topic owntracks/user/dev, return (user, dev) tuple."""
    parts = topic.split('/')
    dev_id_format = ''
    if pretty:
        dev_id_format = '{} {}'
    else:
        dev_id_format = '{}_{}'
    dev_id = slugify(dev_id_format.format(parts[1], parts[2]))
    host_name = parts[1]
    return (host_name, dev_id)


def _parse_see_args(topic, data):
    """Parse the OwnTracks location parameters, into the format see expects."""
    (host_name, dev_id) = parse_topic(topic, False)
    kwargs = {
        'dev_id': dev_id,
        'host_name': host_name,
        'gps': (data[WAYPOINT_LAT_KEY], data[WAYPOINT_LON_KEY])
    }
    if 'acc' in data:
        kwargs['gps_accuracy'] = data['acc']
    if 'batt' in data:
        kwargs['battery'] = data['batt']
    return dev_id, kwargs


def _set_gps_from_zone(kwargs, location, zone):
    """Set the see parameters from the zone parameters."""
    if zone is not None:
        kwargs['gps'] = (
            zone.attributes['latitude'],
            zone.attributes['longitude'])
        kwargs['gps_accuracy'] = zone.attributes['radius']
        kwargs['location_name'] = location
    return kwargs
