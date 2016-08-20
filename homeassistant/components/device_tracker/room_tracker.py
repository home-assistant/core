"""
Support for tracking devices indoors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.room_tracker/
"""
import json
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    YAML_DEVICES,
    CONF_TRACK_NEW,
    PLATFORM_SCHEMA,
    load_config
)
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.util import convert, dt, slugify

DEPENDENCIES = ['mqtt']

_LOGGER = logging.getLogger(__name__)

CONF_TOPIC = 'topic'
CONF_TIMEOUT = 'timeout'

DEFAULT_TOPIC = 'room_presence'
DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOPIC, default=DEFAULT_TOPIC): cv.string,
    vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int
})


def setup_scanner(hass, config, see):
    """Setup a room presence tracker."""
    devices = {}

    def validate_payload(payload):
        """Validate MQTT payload."""
        try:
            data = json.loads(payload)
        except ValueError:
            # if invalid JSON
            _LOGGER.error('Unable to parse payload as JSON: %s', payload)
            return None
        if not isinstance(data, dict):
            _LOGGER.debug('Skipping update for following data '
                          'because of malformatted data: %s',
                          data)
            return None
        if 'id' not in data or 'distance' not in data:
            _LOGGER.debug('Skipping update for following data'
                          'because of missing id or distance: %s',
                          data)
            return None

        return data

    def see_device(mac, room, distance, name=None):
        """Check the seen device against other sightings."""
        if mac in devs_donot_track:
            return
        elif mac in devs_to_track:
            if mac in devices:
                # update tracked device
                device = devices.get(mac)
                timediff = dt.utcnow() - device.get('updated')
                # update if:
                # device is in the same room OR
                # device is closer to another room OR
                # last update from other room was too long ago
                if device.get('room') == room \
                        or distance < device.get('distance') \
                        or timediff.seconds >= config.get(CONF_TIMEOUT):
                    _LOGGER.debug("Updating device %s", mac)
                    devices[mac] = _create_device_dict(room, distance)
                else:
                    return
            else:
                # create a new tracked device
                _LOGGER.debug("Adding device %s to the cache", mac)
                devices[mac] = _create_device_dict(room, distance)
        elif track_new:
            _LOGGER.info("Discovered new device %s", mac)
            devs_to_track.append(mac)
            devices[mac] = _create_device_dict(room, distance)
        else:
            # do not add new devices
            return

        see(mac=mac, host_name=name, room_name=room)

    def room_location_update(topic, payload, qos):
        """MQTT message received."""
        data = validate_payload(payload)
        if not data:
            return

        parsed_data = _parse_update_data(topic, data)
        see_device(**parsed_data)

    yaml_path = hass.config.path(YAML_DEVICES)
    devs_to_track = []
    devs_donot_track = []

    # Load all known devices.
    # We just need the devices so set consider_home and home range
    # to 0
    for device in load_config(yaml_path, hass, 0, 0):
        # check if the device has a MAC
        if device.mac:
            if device.track:
                devs_to_track.append(device.mac)
            else:
                devs_donot_track.append(device.mac)

    # if track new devices is true discover new devices
    # on every scan.
    track_new = convert(config.get(CONF_TRACK_NEW), bool,
                        len(devs_to_track) == 0)
    if not devs_to_track and not track_new:
        _LOGGER.warning("No devices to track!")
        return False

    topic = config.get(CONF_TOPIC) + '/+'
    mqtt.subscribe(hass, topic, room_location_update, 1)

    return True


def _parse_update_data(topic, data):
    """Parse the room presence update."""
    parts = topic.split('/')
    room = parts[1]
    name = data.get('name')
    mac = slugify(data.get('id')).upper()
    distance = data.get('distance')
    parsed_data = {
        'mac': mac,
        'name': name,
        'room': room,
        'distance': distance
    }
    return parsed_data


def _create_device_dict(room, distance):
    return {
        'room': room,
        'distance': distance,
        'updated': dt.utcnow()
    }
