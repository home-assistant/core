"""Support for DSMR Reader through MQTT."""

from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util import slugify

from .const import DOMAIN
from .definitions import SENSORS, DSMRReaderSensorEntityDescription


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up DSMR Reader sensors from config entry."""
    async_add_entities(DSMRSensor(description, config_entry) for description in SENSORS)


class DSMRSensor(SensorEntity):
    """Representation of a DSMR sensor that is updated via MQTT."""

    _attr_has_entity_name = True
    entity_description: DSMRReaderSensorEntityDescription

    def __init__(
        self, description: DSMRReaderSensorEntityDescription, config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = f"{config_entry.entry_id}-{slug}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            if message.payload == "":
                self._attr_native_value = None
            elif self.entity_description.state is not None:
                # Perform optional additional parsing
                self._attr_native_value = self.entity_description.state(message.payload)
            else:
                self._attr_native_value = message.payload

            self.async_write_ha_state()

        try:
            await mqtt.async_subscribe(
                self.hass, self.entity_description.key, message_received, 1
            )
        except HomeAssistantError:
            async_create_issue(
                self.hass,
                DOMAIN,
                f"cannot_subscribe_mqtt_topic_{self.entity_description.key}",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="cannot_subscribe_mqtt_topic",
                translation_placeholders={
                    "topic": self.entity_description.key,
                    "topic_title": self.entity_description.key.split("/")[-1],
                },
            )
