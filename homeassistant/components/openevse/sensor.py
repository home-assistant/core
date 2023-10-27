"""Support for OpenEVSE through MQTT."""
from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .definitions import SENSORS, OpenEVSESensorEntityDescription
from .entity import OpenEVSEEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenEVSE sensors from config entry."""
    async_add_entities(
        OpenEVSESensor(description, config_entry) for description in SENSORS
    )


class OpenEVSESensor(OpenEVSEEntity, SensorEntity):
    """Representation of a OpenEVSE sensor that is updated via MQTT."""

    _attr_has_entity_name = True
    entity_description: OpenEVSESensorEntityDescription

    def __init__(
        self, description: OpenEVSESensorEntityDescription, config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description, config_entry)

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            _LOGGER.debug("Message received on %s: %s", self.entity_id, message)
            if message.payload == "":
                self._attr_native_value = None
            elif self.entity_description.state is not None:
                # Perform optional additional parsing
                self._attr_native_value = self.entity_description.state(message.payload)
            else:
                self._attr_native_value = message.payload

            self.async_write_ha_state()

        subtopic = self.entity_description.topic or self.entity_description.key
        # TODO: Prefix topic with base topic obtained via discovery
        topic = f"{self.mqtt_base_topic}/{subtopic}"
        _LOGGER.debug("Entity %s subscribing to topic %s", self.entity_id, topic)
        await mqtt.async_subscribe(self.hass, topic, message_received, 1)
