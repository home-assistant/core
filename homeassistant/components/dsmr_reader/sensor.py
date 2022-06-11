"""Support for DSMR Reader through MQTT."""
from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import DOMAIN
from .definitions import SENSORS, DSMRReaderSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up DSMR Reader sensors via configuration.yaml and show deprecation warning."""
    _LOGGER.warning(
        "DSMR Reader yaml config is now deprecated and is being imported. "
        "Please remove it from configuration.yaml"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DSMR Reader sensors from config entry."""
    async_add_entities(DSMRSensor(description) for description in SENSORS)


class DSMRSensor(SensorEntity):
    """Representation of a DSMR sensor that is updated via MQTT."""

    entity_description: DSMRReaderSensorEntityDescription

    def __init__(self, description: DSMRReaderSensorEntityDescription) -> None:
        """Initialize the sensor."""
        self.entity_description = description

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"

    async def async_added_to_hass(self) -> None:
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
