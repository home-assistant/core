"""Base entity class and helpers for Victron Energy Home Assistant integration."""

import logging
from typing import Any

from paho.mqtt.client import MQTTMessage

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityCategory
from homeassistant.helpers.template import Template

from .const import DOMAIN
from .types import DeviceKey

_LOGGER = logging.getLogger(__name__)


class VictronBaseEntity(Entity):
    """Base class for Victron Energy entities."""

    _manager: Any
    _device_key: DeviceKey
    _device_info: dict[str, Any]
    _platform: str

    _state_topic: str | None
    _value_template: Template | None

    def _parse_base_config(self, config: dict[str, Any]) -> None:
        """Parse common configuration fields from the config dictionary."""
        self._attr_device_class = config.get("device_class")
        self._attr_entity_registry_enabled_default = bool(
            config.get("enabled_by_default", True)
        )
        self._attr_icon = config.get("icon")
        self._attr_name = config.get("name")
        # Set entity category for diagnostic entities
        entity_category = config.get("entity_category")
        if entity_category == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            self._attr_entity_category = None

        self._state_topic = config.get("state_topic")
        value_template = config.get("value_template")
        if value_template:
            try:
                self._value_template = Template(value_template, self._manager.hass)
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Failed to create value template for entity %s",
                    self._attr_unique_id,
                    exc_info=True,
                )
                self._value_template = None
        else:
            self._value_template = None

    def __init__(
        self,
        manager,
        device_key: DeviceKey,
        device_info: dict[str, Any],
        unique_id: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize the base entity.

        Args:
            manager: The VictronMqttManager instance managing this entity.
            device_key: The DeviceKey tuple (domain, identifier) for this device.
            device_info: The device information dictionary from discovery/config.
            unique_id: The unique identifier for this entity.
            config: The entity configuration dictionary.

        """
        super().__init__()
        self._manager = manager
        self._device_key = device_key
        self._device_info = device_info
        self._platform = config.get("platform", "unknown")
        self._attr_unique_id = unique_id

        self._parse_base_config(config)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update the entity configuration. Override in subclasses for more fields."""
        self._parse_base_config(config)

    def handle_mqtt_message(self, msg: MQTTMessage) -> None:
        """Handle new MQTT message. Override in subclasses."""

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to hass."""
        if self._state_topic is not None:
            self._manager.register_entity_for_topic(str(self._state_topic), self)
            self._manager.subscribe_topic(str(self._state_topic))

        # Ensure device is created in the device registry
        device_info = self.device_info
        device_registry = dr.async_get(self.hass)
        config_entry_id = self.platform.config_entry.entry_id
        device_registry.async_get_or_create(
            config_entry_id=config_entry_id, **device_info
        )

        entity_registry = er.async_get(self.hass)
        entity_registry.async_update_entity(
            self.entity_id, new_entity_id=f"{self._platform}.{self._attr_unique_id}"
        )

    @property
    def should_poll(self) -> bool:
        """Return False as this entity is updated via MQTT messages."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for grouping entities."""
        via_device = self._device_info.get("via_device")
        if via_device is not None:
            return DeviceInfo(
                identifiers={self._device_key},
                manufacturer=str(self._device_info.get("manufacturer", "")),
                model=str(self._device_info.get("model", "")),
                name=str(self._device_info.get("name", "")),
                via_device=(DOMAIN, str(via_device)),
            )
        return DeviceInfo(
            identifiers={self._device_key},
            manufacturer=str(self._device_info.get("manufacturer", "")),
            model=str(self._device_info.get("model", "")),
            name=str(self._device_info.get("name", "")),
        )
