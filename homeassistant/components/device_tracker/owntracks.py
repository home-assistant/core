"""
Support the OwnTracks platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.owntracks/
"""
import asyncio
import json
import logging
import base64
from collections import defaultdict

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.components.mqtt as mqtt
from homeassistant.const import STATE_HOME
from homeassistant.util import convert, slugify
from homeassistant.components import zone as zone_comp
from homeassistant.components.device_tracker import PLATFORM_SCHEMA

DEPENDENCIES = ['mqtt']
REQUIREMENTS = ['libnacl==1.5.0']

_LOGGER = logging.getLogger(__name__)

BEACON_DEV_ID = 'beacon'

CONF_MAX_GPS_ACCURACY = 'max_gps_accuracy'
CONF_SECRET = 'secret'
CONF_WAYPOINT_IMPORT = 'waypoints'
CONF_WAYPOINT_WHITELIST = 'waypoint_whitelist'

EVENT_TOPIC = 'owntracks/+/+/event'

LOCATION_TOPIC = 'owntracks/+/+'

VALIDATE_LOCATION = 'location'
VALIDATE_TRANSITION = 'transition'
VALIDATE_WAYPOINTS = 'waypoints'

WAYPOINT_LAT_KEY = 'lat'
WAYPOINT_LON_KEY = 'lon'
WAYPOINT_TOPIC = 'owntracks/{}/{}/waypoint'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
    vol.Optional(CONF_WAYPOINT_IMPORT, default=True): cv.boolean,
    vol.Optional(CONF_WAYPOINT_WHITELIST): vol.All(
        cv.ensure_list, [cv.string]),
    vol.Optional(CONF_SECRET): vol.Any(
        vol.Schema({vol.Optional(cv.string): cv.string}),
        cv.string)
})


def get_cipher():
    """Return decryption function and length of key.

    Async friendly.
    """
    from libnacl import crypto_secretbox_KEYBYTES as KEYLEN
    from libnacl.secret import SecretBox

    def decrypt(ciphertext, key):
        """Decrypt ciphertext using key."""
        return SecretBox(key).decrypt(ciphertext)
    return (KEYLEN, decrypt)


@asyncio.coroutine
def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up an OwnTracks tracker."""
    max_gps_accuracy = config.get(CONF_MAX_GPS_ACCURACY)
    waypoint_import = config.get(CONF_WAYPOINT_IMPORT)
    waypoint_whitelist = config.get(CONF_WAYPOINT_WHITELIST)
    secret = config.get(CONF_SECRET)

    mobile_beacons_active = defaultdict(list)
    regions_entered = defaultdict(list)

    def decrypt_payload(topic, ciphertext):
        """Decrypt encrypted payload."""
        try:
            keylen, decrypt = get_cipher()
        except OSError:
            _LOGGER.warning(
                "Ignoring encrypted payload because libsodium not installed")
            return None

        if isinstance(secret, dict):
            key = secret.get(topic)
        else:
            key = secret

        if key is None:
            _LOGGER.warning(
                "Ignoring encrypted payload because no decryption key known "
                "for topic %s", topic)
            return None

        key = key.encode("utf-8")
        key = key[:keylen]
        key = key.ljust(keylen, b'\0')

        try:
            ciphertext = base64.b64decode(ciphertext)
            message = decrypt(ciphertext, key)
            message = message.decode("utf-8")
            _LOGGER.debug("Decrypted payload: %s", message)
            return message
        except ValueError:
            _LOGGER.warning(
                "Ignoring encrypted payload because unable to decrypt using "
                "key for topic %s", topic)
            return None

    # pylint: disable=too-many-return-statements
    def validate_payload(topic, payload, data_type):
        """Validate the OwnTracks payload."""
        try:
            data = json.loads(payload)
        except ValueError:
            # If invalid JSON
            _LOGGER.error("Unable to parse payload as JSON: %s", payload)
            return None

        if isinstance(data, dict) and \
           data.get('_type') == 'encrypted' and \
           'data' in data:
            plaintext_payload = decrypt_payload(topic, data['data'])
            if plaintext_payload is None:
                return None
            else:
                return validate_payload(topic, plaintext_payload, data_type)

        if not isinstance(data, dict) or data.get('_type') != data_type:
            _LOGGER.debug("Skipping %s update for following data "
                          "because of missing or malformatted data: %s",
                          data_type, data)
            return None
        if data_type == VALIDATE_TRANSITION or data_type == VALIDATE_WAYPOINTS:
            return data
        if max_gps_accuracy is not None and \
                convert(data.get('acc'), float, 0.0) > max_gps_accuracy:
            _LOGGER.info("Ignoring %s update because expected GPS "
                         "accuracy %s is not met: %s",
                         data_type, max_gps_accuracy, payload)
            return None
        if convert(data.get('acc'), float, 1.0) == 0.0:
            _LOGGER.warning(
                "Ignoring %s update because GPS accuracy is zero: %s",
                data_type, payload)
            return None

        return data

    @callback
    def async_owntracks_location_update(topic, payload, qos):
        """MQTT message received."""
        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typelocation
        data = validate_payload(topic, payload, VALIDATE_LOCATION)
        if not data:
            return

        dev_id, kwargs = _parse_see_args(topic, data)

        if regions_entered[dev_id]:
            _LOGGER.debug(
                "Location update ignored, inside region %s",
                regions_entered[-1])
            return

        hass.async_add_job(async_see(**kwargs))
        async_see_beacons(dev_id, kwargs)

    @callback
    def async_owntracks_event_update(topic, payload, qos):
        """Handle MQTT event (geofences)."""
        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typetransition
        data = validate_payload(topic, payload, VALIDATE_TRANSITION)
        if not data:
            return

        if data.get('desc') is None:
            _LOGGER.error(
                "Location missing from `Entering/Leaving` message - "
                "please turn `Share` on in OwnTracks app")
            return
        # OwnTracks uses - at the start of a beacon zone
        # to switch on 'hold mode' - ignore this
        location = data['desc'].lstrip("-")
        if location.lower() == 'home':
            location = STATE_HOME

        dev_id, kwargs = _parse_see_args(topic, data)

        def enter_event():
            """Execute enter event."""
            zone = hass.states.get("zone.{}".format(slugify(location)))
            if zone is None and data.get('t') == 'b':
                # Not a HA zone, and a beacon so assume mobile
                beacons = mobile_beacons_active[dev_id]
                if location not in beacons:
                    beacons.append(location)
                _LOGGER.info("Added beacon %s", location)
            else:
                # Normal region
                regions = regions_entered[dev_id]
                if location not in regions:
                    regions.append(location)
                _LOGGER.info("Enter region %s", location)
                _set_gps_from_zone(kwargs, location, zone)

            hass.async_add_job(async_see(**kwargs))
            async_see_beacons(dev_id, kwargs)

        def leave_event():
            """Execute leave event."""
            regions = regions_entered[dev_id]
            if location in regions:
                regions.remove(location)
            new_region = regions[-1] if regions else None

            if new_region:
                # Exit to previous region
                zone = hass.states.get(
                    "zone.{}".format(slugify(new_region)))
                _set_gps_from_zone(kwargs, new_region, zone)
                _LOGGER.info("Exit to %s", new_region)
                hass.async_add_job(async_see(**kwargs))
                async_see_beacons(dev_id, kwargs)

            else:
                _LOGGER.info("Exit to GPS")
                # Check for GPS accuracy
                valid_gps = True
                if 'acc' in data:
                    if data['acc'] == 0.0:
                        valid_gps = False
                        _LOGGER.warning(
                            "Ignoring GPS in region exit because accuracy"
                            "is zero: %s", payload)
                    if (max_gps_accuracy is not None and
                            data['acc'] > max_gps_accuracy):
                        valid_gps = False
                        _LOGGER.info(
                            "Ignoring GPS in region exit because expected "
                            "GPS accuracy %s is not met: %s",
                            max_gps_accuracy, payload)
                if valid_gps:
                    hass.async_add_job(async_see(**kwargs))
                    async_see_beacons(dev_id, kwargs)

            beacons = mobile_beacons_active[dev_id]
            if location in beacons:
                beacons.remove(location)
                _LOGGER.info("Remove beacon %s", location)

        if data['event'] == 'enter':
            enter_event()
        elif data['event'] == 'leave':
            leave_event()
        else:
            _LOGGER.error(
                "Misformatted mqtt msgs, _type=transition, event=%s",
                data['event'])
            return

    @callback
    def async_owntracks_waypoint_update(topic, payload, qos):
        """List of waypoints published by a user."""
        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typewaypoints
        data = validate_payload(topic, payload, VALIDATE_WAYPOINTS)
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
            hass.async_add_job(zone.async_update_ha_state())

    @callback
    def async_see_beacons(dev_id, kwargs_param):
        """Set active beacons to the current location."""
        kwargs = kwargs_param.copy()
        # the battery state applies to the tracking device, not the beacon
        kwargs.pop('battery', None)
        for beacon in mobile_beacons_active[dev_id]:
            kwargs['dev_id'] = "{}_{}".format(BEACON_DEV_ID, beacon)
            kwargs['host_name'] = beacon
            hass.async_add_job(async_see(**kwargs))

    yield from mqtt.async_subscribe(
        hass, LOCATION_TOPIC, async_owntracks_location_update, 1)
    yield from mqtt.async_subscribe(
        hass, EVENT_TOPIC, async_owntracks_event_update, 1)

    if waypoint_import:
        if waypoint_whitelist is None:
            yield from mqtt.async_subscribe(
                hass, WAYPOINT_TOPIC.format('+', '+'),
                async_owntracks_waypoint_update, 1)
        else:
            for whitelist_user in waypoint_whitelist:
                yield from mqtt.async_subscribe(
                    hass, WAYPOINT_TOPIC.format(whitelist_user, '+'),
                    async_owntracks_waypoint_update, 1)

    return True


def parse_topic(topic, pretty=False):
    """Parse an MQTT topic owntracks/user/dev, return (user, dev) tuple.

    Async friendly.
    """
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
    """Parse the OwnTracks location parameters, into the format see expects.

    Async friendly.
    """
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
    """Set the see parameters from the zone parameters.

    Async friendly.
    """
    if zone is not None:
        kwargs['gps'] = (
            zone.attributes['latitude'],
            zone.attributes['longitude'])
        kwargs['gps_accuracy'] = zone.attributes['radius']
        kwargs['location_name'] = location
    return kwargs
