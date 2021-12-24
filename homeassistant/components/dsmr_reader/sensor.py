"""Support for DSMR Reader through MQTT."""
from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.util import slugify

from .definitions import SENSORS, DSMRReaderSensorEntityDescription

DOMAIN = "dsmr_reader"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up DSMR Reader sensors."""
    async_add_entities(DSMRSensor(description) for description in SENSORS)


class DSMRSensor(SensorEntity):
    """Representation of a DSMR sensor that is updated via MQTT."""

    entity_description: DSMRReaderSensorEntityDescription

    def __init__(self, description: DSMRReaderSensorEntityDescription) -> None:
        """Initialize the sensor."""
        self.entity_description = description

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(message.payload)
            else:
                self._attr_native_value = message.payload

            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )
