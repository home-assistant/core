"""Support for DSMR Reader through MQTT."""
from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.util import slugify

from .definitions import DEFINITIONS

DOMAIN = "dsmr_reader"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up DSMR Reader sensors."""

    sensors = []
    for topic in DEFINITIONS:
        sensors.append(DSMRSensor(topic))

    async_add_entities(sensors)


class DSMRSensor(SensorEntity):
    """Representation of a DSMR sensor that is updated via MQTT."""

    def __init__(self, topic):
        """Initialize the sensor."""

        self._definition = DEFINITIONS[topic]

        self._entity_id = slugify(topic.replace("/", "_"))
        self._topic = topic

        self._name = self._definition.get("name", topic.split("/")[-1])
        self._device_class = self._definition.get("device_class")
        self._enable_default = self._definition.get("enable_default")
        self._unit_of_measurement = self._definition.get("unit")
        self._icon = self._definition.get("icon")
        self._transform = self._definition.get("transform")
        self._state = None

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""

            if self._transform is not None:
                self._state = self._transform(message.payload)
            else:
                self._state = message.payload

            self.async_write_ha_state()

        await mqtt.async_subscribe(self.hass, self._topic, message_received, 1)

    @property
    def name(self):
        """Return the name of the sensor supplied in constructor."""
        return self._name

    @property
    def entity_id(self):
        """Return the entity ID for this sensor."""
        return f"sensor.{self._entity_id}"

    @property
    def state(self):
        """Return the current state of the entity."""
        return self._state

    @property
    def device_class(self):
        """Return the device_class of this sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of this sensor."""
        return self._unit_of_measurement

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enable_default

    @property
    def icon(self):
        """Return the icon of this sensor."""
        return self._icon
