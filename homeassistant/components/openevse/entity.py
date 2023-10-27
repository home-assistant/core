"""Support for OpenEVSE through MQTT."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.util import slugify

from .const import (
    BRAND,
    CONF_BASE_TOPIC,
    CONF_CONFIG_URL,
    DEVICE_SUGGESTED_AREA,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class OpenEVSEEntity(Entity):
    """Base entity class for platforms to inherit from."""

    _attr_has_entity_name = True
    entity_description: EntityDescription
    mqtt_base_topic: str

    def __init__(
        self, description: EntityDescription, config_entry: ConfigEntry
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        # TODO: Figure out how to prefix all the entity names with the device name

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = f"{config_entry.entry_id}-{slug}"

        _LOGGER.debug("Config entry: %s", config_entry.as_dict())
        self.mqtt_base_topic = config_entry.data[CONF_BASE_TOPIC]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer=BRAND,
            model=BRAND,
            name=BRAND,
            configuration_url=config_entry.data[CONF_CONFIG_URL],
            suggested_area=DEVICE_SUGGESTED_AREA,
        )
