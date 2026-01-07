"""Base entity class and helpers for Victron Energy Home Assistant integration."""

import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.template import Template

if TYPE_CHECKING:
    from . import VictronMqttManager
from .const import DOMAIN
from .types import DeviceKey

_LOGGER = logging.getLogger(__name__)


class VictronBaseEntity(Entity):
    """Base class for Victron Energy entities."""

    _attr_has_entity_name = True

    _manager: "VictronMqttManager"
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
        manager: "VictronMqttManager",
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
        prev_state_topic = self._state_topic
        self._parse_base_config(config)
        if self._state_topic != prev_state_topic:
            self._manager.unsubscribe_entity(self)

        # This will also subscribe to the state topic
        self.set_available(True)

    def handle_mqtt_message(self, topic: str, payload: bytes) -> None:
        """Handle new MQTT message. Override in subclasses."""

    def set_available(self, available: bool) -> None:
        """Set entity availability state."""
        if self._attr_available != available:
            self._attr_available = available
            self.schedule_update_ha_state()
            if available:
                self._manager.subscribe_entity(self)
            else:
                self._manager.unsubscribe_entity(self)

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topic when added to Home Assistant."""
        self._manager.register_entity(self)
        entity_registry = er.async_get(self.hass)
        entity_registry.async_update_entity(
            self.entity_id, new_entity_id=f"{self._platform}.{self._attr_unique_id}"
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from MQTT topic when removed from Home Assistant."""
        self._manager.unregister_entity(self)

    def _parse_payload(self, payload: bytes) -> Any:
        """Try to convert the payload to a usable value.

        Parses the payload using the value template if defined. If there is no template,
        attempt to parse the payload as JSON and extract the 'value' field. If that fails,
        return the raw payload.

        Args:
            payload: The raw MQTT payload as a string.

        Returns:
            The parsed value after applying the value template, or the raw payload.

        """
        try:
            payload_str = payload.decode()
        except (UnicodeDecodeError, AttributeError):
            _LOGGER.error(
                "Unable to decode payload for binary sensor %s: %s",
                self.unique_id,
                payload,
            )
            return None

        _LOGGER.debug(
            "Received MQTT message for %s / %s: %s",
            self._attr_name,
            self._attr_unique_id,
            payload_str,
        )
        # Handle empty payload immediately - set entity to unknown
        if not payload_str.strip():
            return None

        # Try to parse the _value_template when it is set
        if self._value_template:
            try:
                return self._value_template.async_render_with_possible_json_value(
                    payload_str
                )
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Failed to render value template for entity %s with payload: %s",
                    self._attr_unique_id,
                    payload_str,
                )

        # Try to parse the payload as JSON and extract the 'value' field
        try:
            json_payload = json.loads(payload_str)
            if isinstance(json_payload, dict):
                return json_payload.get("value", payload_str)
        except json.JSONDecodeError as err:
            _LOGGER.debug("Failed to decode message JSON: %s", err)
        else:
            return json_payload

        # End with returning the raw payload string when no other parsing succeeded
        return payload_str

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

    @property
    def state_topic(self) -> str | None:
        """Return the MQTT state topic for this entity."""
        return self._state_topic

    @property
    def device_key(self) -> DeviceKey:
        """Return the device key for this entity."""
        return self._device_key
