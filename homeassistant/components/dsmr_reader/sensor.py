"""Support for DSMR Reader through MQTT."""
import logging

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt, slugify

from .definitions import DEFINITIONS

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dsmr_reader"
ATTR_UPDATED = "updated"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up DSMR Reader sensors."""

    sensors = []
    for k in DEFINITIONS:
        sensors.append(DSMRSensor(k))

    async_add_entities(sensors)


class DSMRSensor(Entity):
    """Representation of a DSMR sensor that is updated via MQTT."""

    def __init__(self, topic):
        """Initialize the sensor."""

        self._name = ""
        self._entity_id = slugify(topic.replace("/", "_"))
        self._friendly_name = ""
        self._icon = ""
        self._unit_of_measurement = ""
        self._state = 0
        self._topic = topic
        self._updated = dt.utcnow()

        self._definition = {}
        if topic in DEFINITIONS:
            self._definition = DEFINITIONS[topic]

        parts = topic.split("/")
        self._name = parts[-1]

        if "unit" in self._definition:
            self._unit_of_measurement = self._definition["unit"]
        if "icon" in self._definition:
            self._icon = self._definition["icon"]
        if "name" in self._definition:
            self._friendly_name = self._definition["name"]

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""

        @callback
        def update_state(value):
            """Update the sensor state."""
            self._state = value
            self._updated = dt.utcnow()
            self.async_schedule_update_ha_state()

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            update_state(msg.payload)

        return await mqtt.async_subscribe(self.hass, self._topic, message_received, 1)

    @property
    def name(self):
        """Return the name of the sensor supplied in constructor."""
        return self._friendly_name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_UPDATED: self._updated}

    @property
    def entity_id(self):
        """Return the entity ID of the sensor."""
        return f"sensor.{self._entity_id}"

    @property
    def state(self):
        """Return the current state of the entity."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of this sensor."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return self._icon
