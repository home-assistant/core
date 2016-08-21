"""
Support for MQTT room presence detection.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mqtt_room/
"""
import logging
import json

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, STATE_UNKNOWN
from homeassistant.components.mqtt import CONF_STATE_TOPIC
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt, slugify

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_DEVICE_ID = 'device_id'
CONF_TIMEOUT = 'timeout'

DEFAULT_TOPIC = 'room_presence'
DEFAULT_TIMEOUT = 5
DEFAULT_NAME = 'Room Sensor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_STATE_TOPIC, default=DEFAULT_TOPIC): cv.string,
    vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

MQTT_PAYLOAD = vol.Schema(vol.All(json.loads, vol.Schema({
    vol.Required('id'): cv.string,
    vol.Required('distance'): vol.Coerce(float)
}, extra=vol.ALLOW_EXTRA)))


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup MQTT Sensor."""
    add_devices_callback([MQTTRoomSensor(
        hass,
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_DEVICE_ID),
        config.get(CONF_TIMEOUT)
    )])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MQTTRoomSensor(Entity):
    """Representation of a room sensor that is updated via MQTT."""

    def __init__(self, hass, name, state_topic, device_id, timeout):
        """Initialize the sensor."""
        self._state = STATE_UNKNOWN
        self._hass = hass
        self._name = name
        self._state_topic = state_topic + '/+'
        self._device_id = slugify(device_id).upper()
        self._timeout = timeout
        self._distance = None
        self._updated = None

        def update_state(device_id, room, distance):
            """Update the sensor state."""
            self._state = room
            self._distance = distance
            self._updated = dt.utcnow()

            self.update_ha_state()

        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            try:
                data = MQTT_PAYLOAD(payload)
            except vol.MultipleInvalid as error:
                _LOGGER.debug('skipping update because of malformatted '
                              'data: %s', error)
                return

            device = _parse_update_data(topic, data)
            if device.get('device_id') == self._device_id:
                if self._distance is None or self._updated is None:
                    update_state(**device)
                else:
                    # update if:
                    # device is in the same room OR
                    # device is closer to another room OR
                    # last update from other room was too long ago
                    timediff = dt.utcnow() - self._updated
                    if device.get('room') == self._state \
                            or device.get('distance') < self._distance \
                            or timediff.seconds >= self._timeout:
                        update_state(**device)

        mqtt.subscribe(hass, self._state_topic, message_received, 1)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'distance': self._distance
        }

    @property
    def state(self):
        """Return the current room of the entity."""
        return self._state


def _parse_update_data(topic, data):
    """Parse the room presence update."""
    parts = topic.split('/')
    room = parts[-1]
    device_id = slugify(data.get('id')).upper()
    distance = data.get('distance')
    parsed_data = {
        'device_id': device_id,
        'room': room,
        'distance': distance
    }
    return parsed_data
