"""Support for OpenEVSE through MQTT."""
from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .definitions import BINARY_SENSORS, OpenEVSEBinarySensorEntityDescription
from .entity import OpenEVSEEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenEVSE binary sensors from config entry."""
    async_add_entities(
        OpenEVSEBinarySensor(description, config_entry)
        for description in BINARY_SENSORS
    )


class OpenEVSEBinarySensor(OpenEVSEEntity, BinarySensorEntity):
    """Representation of a OpenEVSE binary sensor that is updated via MQTT."""

    _attr_has_entity_name = True
    entity_description: OpenEVSEBinarySensorEntityDescription
    state_is_on: bool | None = None

    def __init__(
        self,
        description: OpenEVSEBinarySensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description, config_entry)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.state_is_on is not None:
            return self.state_is_on
        return None

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            _LOGGER.debug("Message received on %s: %s", self.entity_id, message)
            if message.payload == "":
                self.state_is_on = None
            elif message.payload == "0":
                self.state_is_on = False
            elif message.payload == "1":
                self.state_is_on = True
            else:
                _LOGGER.error(
                    "Received unexpected MQTT value '%s' for binary sensor '%s'",
                    message.payload,
                    self.entity_description.key,
                )

            # self.async_write_ha_state()

        subtopic = self.entity_description.topic or self.entity_description.key
        topic = f"{self.mqtt_base_topic}/{subtopic}"
        _LOGGER.debug("Entity %s subscribing to topic %s", self.entity_id, topic)
        await mqtt.async_subscribe(self.hass, topic, message_received, 1)
