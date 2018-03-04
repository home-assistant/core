"""
Device tracker platform that adds support for OwnTracks over MQTT.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.owntracks/
"""
import asyncio
import base64
import json
import logging
from collections import defaultdict

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.components import zone as zone_comp
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, ATTR_SOURCE_TYPE, SOURCE_TYPE_BLUETOOTH_LE,
    SOURCE_TYPE_GPS
)
from homeassistant.const import STATE_HOME
from homeassistant.core import callback
from homeassistant.util import slugify, decorator

REQUIREMENTS = ['libnacl==1.6.1']

_LOGGER = logging.getLogger(__name__)

HANDLERS = decorator.Registry()

BEACON_DEV_ID = 'beacon'

CONF_MAX_GPS_ACCURACY = 'max_gps_accuracy'
CONF_SECRET = 'secret'
CONF_WAYPOINT_IMPORT = 'waypoints'
CONF_WAYPOINT_WHITELIST = 'waypoint_whitelist'
CONF_MQTT_TOPIC = 'mqtt_topic'
CONF_REGION_MAPPING = 'region_mapping'
CONF_EVENTS_ONLY = 'events_only'

DEPENDENCIES = ['mqtt']

DEFAULT_OWNTRACKS_TOPIC = 'owntracks/#'
REGION_MAPPING = {}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
    vol.Optional(CONF_WAYPOINT_IMPORT, default=True): cv.boolean,
    vol.Optional(CONF_EVENTS_ONLY, default=False): cv.boolean,
    vol.Optional(CONF_MQTT_TOPIC, default=DEFAULT_OWNTRACKS_TOPIC):
        mqtt.valid_subscribe_topic,
    vol.Optional(CONF_WAYPOINT_WHITELIST): vol.All(
        cv.ensure_list, [cv.string]),
    vol.Optional(CONF_SECRET): vol.Any(
        vol.Schema({vol.Optional(cv.string): cv.string}),
        cv.string),
    vol.Optional(CONF_REGION_MAPPING, default=REGION_MAPPING): dict
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
    context = context_from_config(async_see, config)

    @asyncio.coroutine
    def async_handle_mqtt_message(topic, payload, qos):
        """Handle incoming OwnTracks message."""
        try:
            message = json.loads(payload)
        except ValueError:
            # If invalid JSON
            _LOGGER.error("Unable to parse payload as JSON: %s", payload)
            return

        message['topic'] = topic

        yield from async_handle_message(hass, context, message)

    yield from mqtt.async_subscribe(
        hass, context.mqtt_topic, async_handle_mqtt_message, 1)

    return True


def _parse_topic(topic, subscribe_topic):
    """Parse an MQTT topic {sub_topic}/user/dev, return (user, dev) tuple.

    Async friendly.
    """
    subscription = subscribe_topic.split('/')
    try:
        user_index = subscription.index('#')
    except ValueError:
        _LOGGER.error("Can't parse subscription topic: '%s'", subscribe_topic)
        raise

    topic_list = topic.split('/')
    try:
        user, device = topic_list[user_index], topic_list[user_index + 1]
    except IndexError:
        _LOGGER.error("Can't parse topic: '%s'", topic)
        raise

    return user, device


def _parse_see_args(message, subscribe_topic):
    """Parse the OwnTracks location parameters, into the format see expects.

    Async friendly.
    """
    user, device = _parse_topic(message['topic'], subscribe_topic)
    dev_id = slugify('{}_{}'.format(user, device))
    kwargs = {
        'dev_id': dev_id,
        'host_name': user,
        'gps': (message['lat'], message['lon']),
        'attributes': {}
    }
    if 'acc' in message:
        kwargs['gps_accuracy'] = message['acc']
    if 'batt' in message:
        kwargs['battery'] = message['batt']
    if 'vel' in message:
        kwargs['attributes']['velocity'] = message['vel']
    if 'tid' in message:
        kwargs['attributes']['tid'] = message['tid']
    if 'addr' in message:
        kwargs['attributes']['address'] = message['addr']
    if 'cog' in message:
        kwargs['attributes']['course'] = message['cog']
    if 't' in message:
        if message['t'] == 'c':
            kwargs['attributes'][ATTR_SOURCE_TYPE] = SOURCE_TYPE_GPS
        if message['t'] == 'b':
            kwargs['attributes'][ATTR_SOURCE_TYPE] = SOURCE_TYPE_BLUETOOTH_LE

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


def _decrypt_payload(secret, topic, ciphertext):
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


def context_from_config(async_see, config):
    """Create an async context from Home Assistant config."""
    max_gps_accuracy = config.get(CONF_MAX_GPS_ACCURACY)
    waypoint_import = config.get(CONF_WAYPOINT_IMPORT)
    waypoint_whitelist = config.get(CONF_WAYPOINT_WHITELIST)
    secret = config.get(CONF_SECRET)
    region_mapping = config.get(CONF_REGION_MAPPING)
    events_only = config.get(CONF_EVENTS_ONLY)
    mqtt_topic = config.get(CONF_MQTT_TOPIC)

    return OwnTracksContext(async_see, secret, max_gps_accuracy,
                            waypoint_import, waypoint_whitelist,
                            region_mapping, events_only, mqtt_topic)


class OwnTracksContext:
    """Hold the current OwnTracks context."""

    def __init__(self, async_see, secret, max_gps_accuracy, import_waypoints,
                 waypoint_whitelist, region_mapping, events_only, mqtt_topic):
        """Initialize an OwnTracks context."""
        self.async_see = async_see
        self.secret = secret
        self.max_gps_accuracy = max_gps_accuracy
        self.mobile_beacons_active = defaultdict(set)
        self.regions_entered = defaultdict(list)
        self.import_waypoints = import_waypoints
        self.waypoint_whitelist = waypoint_whitelist
        self.region_mapping = region_mapping
        self.events_only = events_only
        self.mqtt_topic = mqtt_topic

    @callback
    def async_valid_accuracy(self, message):
        """Check if we should ignore this message."""
        acc = message.get('acc')

        if acc is None:
            return False

        try:
            acc = float(acc)
        except ValueError:
            return False

        if acc == 0:
            _LOGGER.warning(
                "Ignoring %s update because GPS accuracy is zero: %s",
                message['_type'], message)
            return False

        if self.max_gps_accuracy is not None and \
                acc > self.max_gps_accuracy:
            _LOGGER.info("Ignoring %s update because expected GPS "
                         "accuracy %s is not met: %s",
                         message['_type'], self.max_gps_accuracy,
                         message)
            return False

        return True

    @asyncio.coroutine
    def async_see_beacons(self, hass, dev_id, kwargs_param):
        """Set active beacons to the current location."""
        kwargs = kwargs_param.copy()

        # Mobile beacons should always be set to the location of the
        # tracking device. I get the device state and make the necessary
        # changes to kwargs.
        device_tracker_state = hass.states.get(
            "device_tracker.{}".format(dev_id))

        if device_tracker_state is not None:
            acc = device_tracker_state.attributes.get("gps_accuracy")
            lat = device_tracker_state.attributes.get("latitude")
            lon = device_tracker_state.attributes.get("longitude")
            kwargs['gps_accuracy'] = acc
            kwargs['gps'] = (lat, lon)

        # the battery state applies to the tracking device, not the beacon
        # kwargs location is the beacon's configured lat/lon
        kwargs.pop('battery', None)
        for beacon in self.mobile_beacons_active[dev_id]:
            kwargs['dev_id'] = "{}_{}".format(BEACON_DEV_ID, beacon)
            kwargs['host_name'] = beacon
            yield from self.async_see(**kwargs)


@HANDLERS.register('location')
@asyncio.coroutine
def async_handle_location_message(hass, context, message):
    """Handle a location message."""
    if not context.async_valid_accuracy(message):
        return

    if context.events_only:
        _LOGGER.debug("Location update ignored due to events_only setting")
        return

    dev_id, kwargs = _parse_see_args(message, context.mqtt_topic)

    if context.regions_entered[dev_id]:
        _LOGGER.debug(
            "Location update ignored, inside region %s",
            context.regions_entered[-1])
        return

    yield from context.async_see(**kwargs)
    yield from context.async_see_beacons(hass, dev_id, kwargs)


@asyncio.coroutine
def _async_transition_message_enter(hass, context, message, location):
    """Execute enter event."""
    zone = hass.states.get("zone.{}".format(slugify(location)))
    dev_id, kwargs = _parse_see_args(message, context.mqtt_topic)

    if zone is None and message.get('t') == 'b':
        # Not a HA zone, and a beacon so mobile beacon.
        # kwargs will contain the lat/lon of the beacon
        # which is not where the beacon actually is
        # and is probably set to 0/0
        beacons = context.mobile_beacons_active[dev_id]
        if location not in beacons:
            beacons.add(location)
        _LOGGER.info("Added beacon %s", location)
        yield from context.async_see_beacons(hass, dev_id, kwargs)
    else:
        # Normal region
        regions = context.regions_entered[dev_id]
        if location not in regions:
            regions.append(location)
        _LOGGER.info("Enter region %s", location)
        _set_gps_from_zone(kwargs, location, zone)
        yield from context.async_see(**kwargs)
        yield from context.async_see_beacons(hass, dev_id, kwargs)


@asyncio.coroutine
def _async_transition_message_leave(hass, context, message, location):
    """Execute leave event."""
    dev_id, kwargs = _parse_see_args(message, context.mqtt_topic)
    regions = context.regions_entered[dev_id]

    if location in regions:
        regions.remove(location)

    beacons = context.mobile_beacons_active[dev_id]
    if location in beacons:
        beacons.remove(location)
        _LOGGER.info("Remove beacon %s", location)
        yield from context.async_see_beacons(hass, dev_id, kwargs)
    else:
        new_region = regions[-1] if regions else None
        if new_region:
            # Exit to previous region
            zone = hass.states.get(
                "zone.{}".format(slugify(new_region)))
            _set_gps_from_zone(kwargs, new_region, zone)
            _LOGGER.info("Exit to %s", new_region)
            yield from context.async_see(**kwargs)
            yield from context.async_see_beacons(hass, dev_id, kwargs)
            return

        _LOGGER.info("Exit to GPS")

        # Check for GPS accuracy
        if context.async_valid_accuracy(message):
            yield from context.async_see(**kwargs)
            yield from context.async_see_beacons(hass, dev_id, kwargs)


@HANDLERS.register('transition')
@asyncio.coroutine
def async_handle_transition_message(hass, context, message):
    """Handle a transition message."""
    if message.get('desc') is None:
        _LOGGER.error(
            "Location missing from `Entering/Leaving` message - "
            "please turn `Share` on in OwnTracks app")
        return
    # OwnTracks uses - at the start of a beacon zone
    # to switch on 'hold mode' - ignore this
    location = message['desc'].lstrip("-")

    # Create a layer of indirection for Owntracks instances that may name
    # regions differently than their HA names
    if location in context.region_mapping:
        location = context.region_mapping[location]

    if location.lower() == 'home':
        location = STATE_HOME

    if message['event'] == 'enter':
        yield from _async_transition_message_enter(
            hass, context, message, location)
    elif message['event'] == 'leave':
        yield from _async_transition_message_leave(
            hass, context, message, location)
    else:
        _LOGGER.error(
            "Misformatted mqtt msgs, _type=transition, event=%s",
            message['event'])


@asyncio.coroutine
def async_handle_waypoint(hass, name_base, waypoint):
    """Handle a waypoint."""
    name = waypoint['desc']
    pretty_name = '{} - {}'.format(name_base, name)
    lat = waypoint['lat']
    lon = waypoint['lon']
    rad = waypoint['rad']

    # check zone exists
    entity_id = zone_comp.ENTITY_ID_FORMAT.format(slugify(pretty_name))

    # Check if state already exists
    if hass.states.get(entity_id) is not None:
        return

    zone = zone_comp.Zone(hass, pretty_name, lat, lon, rad,
                          zone_comp.ICON_IMPORT, False)
    zone.entity_id = entity_id
    yield from zone.async_update_ha_state()


@HANDLERS.register('waypoint')
@HANDLERS.register('waypoints')
@asyncio.coroutine
def async_handle_waypoints_message(hass, context, message):
    """Handle a waypoints message."""
    if not context.import_waypoints:
        return

    if context.waypoint_whitelist is not None:
        user = _parse_topic(message['topic'], context.mqtt_topic)[0]

        if user not in context.waypoint_whitelist:
            return

    if 'waypoints' in message:
        wayps = message['waypoints']
    else:
        wayps = [message]

    _LOGGER.info("Got %d waypoints from %s", len(wayps), message['topic'])

    name_base = ' '.join(_parse_topic(message['topic'], context.mqtt_topic))

    for wayp in wayps:
        yield from async_handle_waypoint(hass, name_base, wayp)


@HANDLERS.register('encrypted')
@asyncio.coroutine
def async_handle_encrypted_message(hass, context, message):
    """Handle an encrypted message."""
    plaintext_payload = _decrypt_payload(context.secret, message['topic'],
                                         message['data'])

    if plaintext_payload is None:
        return

    decrypted = json.loads(plaintext_payload)
    decrypted['topic'] = message['topic']

    yield from async_handle_message(hass, context, decrypted)


@HANDLERS.register('lwt')
@HANDLERS.register('configuration')
@HANDLERS.register('beacon')
@HANDLERS.register('cmd')
@HANDLERS.register('steps')
@HANDLERS.register('card')
@asyncio.coroutine
def async_handle_not_impl_msg(hass, context, message):
    """Handle valid but not implemented message types."""
    _LOGGER.debug('Not handling %s message: %s', message.get("_type"), message)


@asyncio.coroutine
def async_handle_unsupported_msg(hass, context, message):
    """Handle an unsupported or invalid message type."""
    _LOGGER.warning('Received unsupported message type: %s.',
                    message.get('_type'))


@asyncio.coroutine
def async_handle_message(hass, context, message):
    """Handle an OwnTracks message."""
    msgtype = message.get('_type')

    handler = HANDLERS.get(msgtype, async_handle_unsupported_msg)

    yield from handler(hass, context, message)
