"""Binary sensor support for Wireless Sensor Tags."""
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_MONITORED_CONDITIONS, STATE_OFF, STATE_ON
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    DOMAIN as WIRELESSTAG_DOMAIN,
    SIGNAL_BINARY_EVENT_UPDATE,
    WirelessTagBaseSensor,
)

# On means in range, Off means out of range
SENSOR_PRESENCE = "presence"

# On means motion detected, Off means clear
SENSOR_MOTION = "motion"

# On means open, Off means closed
SENSOR_DOOR = "door"

# On means temperature become too cold, Off means normal
SENSOR_COLD = "cold"

# On means hot, Off means normal
SENSOR_HEAT = "heat"

# On means too dry (humidity), Off means normal
SENSOR_DRY = "dry"

# On means too wet (humidity), Off means normal
SENSOR_WET = "wet"

# On means light detected, Off means no light
SENSOR_LIGHT = "light"

# On means moisture detected (wet), Off means no moisture (dry)
SENSOR_MOISTURE = "moisture"

# On means tag battery is low, Off means normal
SENSOR_BATTERY = "battery"

# Sensor types: Name, device_class, push notification type representing 'on',
# attr to check
SENSOR_TYPES = {
    SENSOR_PRESENCE: "Presence",
    SENSOR_MOTION: "Motion",
    SENSOR_DOOR: "Door",
    SENSOR_COLD: "Cold",
    SENSOR_HEAT: "Heat",
    SENSOR_DRY: "Too dry",
    SENSOR_WET: "Too wet",
    SENSOR_LIGHT: "Light",
    SENSOR_MOISTURE: "Leak",
    SENSOR_BATTERY: "Low Battery",
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform for a WirelessTags."""
    platform = hass.data.get(WIRELESSTAG_DOMAIN)

    sensors = []
    tags = platform.tags
    for tag in tags.values():
        allowed_sensor_types = tag.supported_binary_events_types
        for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
            if sensor_type in allowed_sensor_types:
                sensors.append(WirelessTagBinarySensor(platform, tag, sensor_type))

    add_entities(sensors, True)


class WirelessTagBinarySensor(WirelessTagBaseSensor, BinarySensorEntity):
    """A binary sensor implementation for WirelessTags."""

    def __init__(self, api, tag, sensor_type):
        """Initialize a binary sensor for a Wireless Sensor Tags."""
        super().__init__(api, tag)
        self._sensor_type = sensor_type
        self._name = f"{self._tag.name} {self.event.human_readable_name}"

    async def async_added_to_hass(self):
        """Register callbacks."""
        tag_id = self.tag_id
        event_type = self.device_class
        mac = self.tag_manager_mac
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_BINARY_EVENT_UPDATE.format(tag_id, event_type, mac),
                self._on_binary_event_callback,
            )
        )

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state == STATE_ON

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._sensor_type

    @property
    def event(self):
        """Binary event of tag."""
        return self._tag.event[self._sensor_type]

    @property
    def principal_value(self):
        """Return value of tag.

        Subclasses need override based on type of sensor.
        """
        return STATE_ON if self.event.is_state_on else STATE_OFF

    def updated_state_value(self):
        """Use raw princial value."""
        return self.principal_value

    @callback
    def _on_binary_event_callback(self, new_tag):
        """Update state from arrived push notification."""
        self._tag = new_tag
        self._state = self.updated_state_value()
        self.async_write_ha_state()
