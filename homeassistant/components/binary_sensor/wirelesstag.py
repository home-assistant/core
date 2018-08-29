"""
Binary sensor support for Wireless Sensor Tags.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.wirelesstag/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.wirelesstag import (
    DOMAIN as WIRELESSTAG_DOMAIN,
    WIRELESSTAG_TYPE_13BIT, WIRELESSTAG_TYPE_WATER,
    WIRELESSTAG_TYPE_ALSPRO,
    WIRELESSTAG_TYPE_WEMO_DEVICE,
    SIGNAL_BINARY_EVENT_UPDATE,
    WirelessTagBaseSensor)
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, STATE_ON, STATE_OFF)
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['wirelesstag']

_LOGGER = logging.getLogger(__name__)

# On means in range, Off means out of range
SENSOR_PRESENCE = 'presence'

# On means motion detected, Off means cear
SENSOR_MOTION = 'motion'

# On means open, Off means closed
SENSOR_DOOR = 'door'

# On means temperature become too cold, Off means normal
SENSOR_COLD = 'cold'

# On means hot, Off means normal
SENSOR_HEAT = 'heat'

# On means too dry (humidity), Off means normal
SENSOR_DRY = 'dry'

# On means too wet (humidity), Off means normal
SENSOR_WET = 'wet'

# On means light detected, Off means no light
SENSOR_LIGHT = 'light'

# On means moisture detected (wet), Off means no moisture (dry)
SENSOR_MOISTURE = 'moisture'

# On means tag battery is low, Off means normal
SENSOR_BATTERY = 'low_battery'

# Sensor types: Name, device_class, push notification type representing 'on',
# attr to check
SENSOR_TYPES = {
    SENSOR_PRESENCE: ['Presence', 'presence', 'is_in_range', {
        "on": "oor",
        "off": "back_in_range"
        }, 2],
    SENSOR_MOTION: ['Motion', 'motion', 'is_moved', {
        "on": "motion_detected",
        }, 5],
    SENSOR_DOOR: ['Door', 'door', 'is_door_open', {
        "on": "door_opened",
        "off": "door_closed"
        }, 5],
    SENSOR_COLD: ['Cold', 'cold', 'is_cold', {
        "on": "temp_toolow",
        "off": "temp_normal"
        }, 4],
    SENSOR_HEAT: ['Heat', 'heat', 'is_heat', {
        "on": "temp_toohigh",
        "off": "temp_normal"
        }, 4],
    SENSOR_DRY: ['Too dry', 'dry', 'is_too_dry', {
        "on": "too_dry",
        "off": "cap_normal"
        }, 2],
    SENSOR_WET: ['Too wet', 'wet', 'is_too_humid', {
        "on": "too_humid",
        "off": "cap_normal"
        }, 2],
    SENSOR_LIGHT: ['Light', 'light', 'is_light_on', {
        "on": "too_bright",
        "off": "light_normal"
        }, 1],
    SENSOR_MOISTURE: ['Leak', 'moisture', 'is_leaking', {
        "on": "water_detected",
        "off": "water_dried",
        }, 1],
    SENSOR_BATTERY: ['Low Battery', 'battery', 'is_battery_low', {
        "on": "low_battery"
        }, 3]
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform for a WirelessTags."""
    platform = hass.data.get(WIRELESSTAG_DOMAIN)

    sensors = []
    tags = platform.tags
    for tag in tags.values():
        allowed_sensor_types = WirelessTagBinarySensor.allowed_sensors(tag)
        for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
            if sensor_type in allowed_sensor_types:
                sensors.append(WirelessTagBinarySensor(platform, tag,
                                                       sensor_type))

    add_entities(sensors, True)
    hass.add_job(platform.install_push_notifications, sensors)


class WirelessTagBinarySensor(WirelessTagBaseSensor, BinarySensorDevice):
    """A binary sensor implementation for WirelessTags."""

    @classmethod
    def allowed_sensors(cls, tag):
        """Return list of allowed sensor types for specific tag type."""
        sensors_map = {
            # 13-bit tag - allows everything but not light and moisture
            WIRELESSTAG_TYPE_13BIT: [
                SENSOR_PRESENCE, SENSOR_BATTERY,
                SENSOR_MOTION, SENSOR_DOOR,
                SENSOR_COLD, SENSOR_HEAT,
                SENSOR_DRY, SENSOR_WET],

            # Moister/water sensor - temperature and moisture only
            WIRELESSTAG_TYPE_WATER: [
                SENSOR_PRESENCE, SENSOR_BATTERY,
                SENSOR_COLD, SENSOR_HEAT,
                SENSOR_MOISTURE],

            # ALS Pro: allows everything, but not moisture
            WIRELESSTAG_TYPE_ALSPRO: [
                SENSOR_PRESENCE, SENSOR_BATTERY,
                SENSOR_MOTION, SENSOR_DOOR,
                SENSOR_COLD, SENSOR_HEAT,
                SENSOR_DRY, SENSOR_WET,
                SENSOR_LIGHT],

            # Wemo are power switches.
            WIRELESSTAG_TYPE_WEMO_DEVICE: [SENSOR_PRESENCE]
        }

        # allow everything if tag type is unknown
        # (i just dont have full catalog of them :))
        tag_type = tag.tag_type
        fullset = SENSOR_TYPES.keys()
        return sensors_map[tag_type] if tag_type in sensors_map else fullset

    def __init__(self, api, tag, sensor_type):
        """Initialize a binary sensor for a Wireless Sensor Tags."""
        super().__init__(api, tag)
        self._sensor_type = sensor_type
        self._name = '{0} {1}'.format(self._tag.name,
                                      SENSOR_TYPES[self._sensor_type][0])
        self._device_class = SENSOR_TYPES[self._sensor_type][1]
        self._tag_attr = SENSOR_TYPES[self._sensor_type][2]
        self.binary_spec = SENSOR_TYPES[self._sensor_type][3]
        self.tag_id_index_template = SENSOR_TYPES[self._sensor_type][4]

    async def async_added_to_hass(self):
        """Register callbacks."""
        tag_id = self.tag_id
        event_type = self.device_class
        async_dispatcher_connect(
            self.hass,
            SIGNAL_BINARY_EVENT_UPDATE.format(tag_id, event_type),
            self._on_binary_event_callback)

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state == STATE_ON

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    @property
    def principal_value(self):
        """Return value of tag.

        Subclasses need override based on type of sensor.
        """
        return (
            STATE_ON if getattr(self._tag, self._tag_attr, False)
            else STATE_OFF)

    def updated_state_value(self):
        """Use raw princial value."""
        return self.principal_value

    @callback
    def _on_binary_event_callback(self, event):
        """Update state from arrive push notification."""
        # state should be 'on' or 'off'
        self._state = event.data.get('state')
        self.async_schedule_update_ha_state()
