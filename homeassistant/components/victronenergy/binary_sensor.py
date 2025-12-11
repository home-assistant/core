"""Binary sensor platform for Victron Energy integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.template import Template

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Energy binary sensors from a config entry."""
    manager = hass.data[DOMAIN][entry.entry_id]
    manager.set_platform_add_entities("binary_sensor", async_add_entities)


class MQTTDiscoveredBinarySensor(BinarySensorEntity):
    """Representation of a discovered MQTT binary sensor."""

    def __init__(self, config: dict[str, Any], unique_id: str, manager) -> None:
        """Initialize the binary sensor."""
        self._manager = manager
        self._attr_name = config.get("name")
        self._state_topic = config.get("state_topic")
        self._value_template = config.get("value_template")
        self._attr_unique_id = unique_id
        self._desired_entity_id = f"binary_sensor.{unique_id}"
        self._attr_entity_id = f"binary_sensor.{unique_id}"
        self._attr_device_class = config.get("device_class")
        self._attr_enabled_by_default = config.get("enabled_by_default", True)
        self._attr_entity_category = None
        self._payload_on = config.get("payload_on", "ON")
        self._payload_off = config.get("payload_off", "OFF")

        # Handle entity category
        entity_category_str = config.get("entity_category")
        if entity_category_str:
            try:
                self._attr_entity_category = EntityCategory(entity_category_str)
            except ValueError:
                _LOGGER.warning(
                    "Invalid entity_category '%s' for binary sensor %s",
                    entity_category_str,
                    unique_id,
                )

        # Store raw device info for device_info property
        self._device_info_raw = config.get("device")

        # Create template if provided
        if self._value_template:
            try:
                self._template = Template(self._value_template, self._manager.hass)
            except Exception as err:
                _LOGGER.error(
                    "Failed to create value template for binary sensor %s: %s",
                    unique_id,
                    err,
                )
                self._template = None
        else:
            self._template = None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for grouping entities."""
        if not self._device_info_raw:
            return None
        device = self._device_info_raw
        identifiers: set[tuple[str, str]] = set()
        raw_identifiers = device.get("identifiers")
        if isinstance(raw_identifiers, list) and len(raw_identifiers) >= 1:
            # Always use DOMAIN as first element, device identifier as second
            identifiers.add((DOMAIN, str(raw_identifiers[0])))

        via_device = device.get("via_device")
        if via_device is not None:
            return DeviceInfo(
                identifiers=identifiers,
                manufacturer=str(device.get("manufacturer", "")),
                model=str(device.get("model", "")),
                name=str(device.get("name", "")),
                via_device=(DOMAIN, str(via_device)),
            )

        return DeviceInfo(
            identifiers=identifiers,
            manufacturer=str(device.get("manufacturer", "")),
            model=str(device.get("model", "")),
            name=str(device.get("name", "")),
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the binary sensor."""
        return self._attr_unique_id

    @property
    def should_poll(self) -> bool:
        """Return False as this entity is updated via MQTT messages."""
        return False

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    def handle_mqtt_message(self, msg) -> None:
        """Handle new MQTT message."""
        try:
            payload = msg.payload.decode()

            # Handle empty payload immediately - set entity to unknown
            if not payload.strip():
                self._attr_is_on = None
                self.schedule_update_ha_state()
                return

            if self._template:
                # Use template to process the payload
                try:
                    processed_value = (
                        self._template.async_render_with_possible_json_value(payload)
                    )
                except Exception as err:
                    _LOGGER.error(
                        "Template error for binary sensor %s: %s", self.unique_id, err
                    )
                    return
            else:
                # No template, use payload directly
                processed_value = payload

            # Handle disconnected/invalid states first (including template result of None)
            if processed_value is None:
                self._attr_is_on = None
            elif processed_value in (
                "unknown",
                "None",
                "null",
                "",
                "unavailable",
                "disconnected",
            ):
                self._attr_is_on = None
            elif isinstance(processed_value, str) and processed_value.lower() in (
                "none",
                "null",
                "n/a",
                "na",
                "unavailable",
            ):
                self._attr_is_on = None
            # Convert to boolean based on payload_on/payload_off
            elif processed_value == self._payload_on:
                self._attr_is_on = True
            elif processed_value == self._payload_off:
                self._attr_is_on = False
            else:
                # Try to parse as JSON boolean or numeric
                try:
                    json_value = json.loads(processed_value)
                    if isinstance(json_value, bool):
                        self._attr_is_on = json_value
                    elif isinstance(json_value, (int, float)):
                        self._attr_is_on = bool(json_value)
                    else:
                        _LOGGER.debug(
                            "Binary sensor %s received unexpected payload: %s",
                            self.unique_id,
                            processed_value,
                        )
                        return
                except json.JSONDecodeError:
                    _LOGGER.debug(
                        "Binary sensor %s received unexpected payload: %s",
                        self.unique_id,
                        processed_value,
                    )
                    return

            # Schedule state update
            self.schedule_update_ha_state()
            _LOGGER.debug(
                "Binary sensor %s updated to: %s (from payload: %s)",
                self.unique_id,
                self._attr_is_on,
                payload,
            )
        except Exception as err:
            _LOGGER.error(
                "Error handling MQTT message for binary sensor %s: %s",
                self.unique_id,
                err,
            )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topic when added to Home Assistant."""
        manager = self._manager
        if self._state_topic is not None:
            manager.register_entity_for_topic(str(self._state_topic), self)
            manager.subscribe_topic(str(self._state_topic))

        # Ensure device is created in the device registry
        await self._ensure_device_registered()

        # Set the entity_id explicitly to match the unique_id using correct registry access
        entity_registry = er.async_get(self.hass)
        entity_registry.async_update_entity(
            self.entity_id, new_entity_id=self._desired_entity_id
        )

    async def _ensure_device_registered(self) -> None:
        """Ensure the device is registered in the device registry."""
        device_info = self.device_info
        if not device_info:
            return

        device_registry = dr.async_get(self.hass)
        config_entry_id = self.platform.config_entry.entry_id

        # Home Assistant automatically handles via_device dependencies
        device_registry.async_get_or_create(
            config_entry_id=config_entry_id, **device_info
        )

    def update_config(self, config: dict[str, Any]) -> None:
        """Update the binary sensor configuration."""
        self._attr_name = config.get("name", self._attr_name)
        self._value_template = config.get("value_template")
        self._attr_device_class = config.get("device_class")
        self._attr_enabled_by_default = config.get("enabled_by_default", True)
        self._payload_on = config.get("payload_on", "ON")
        self._payload_off = config.get("payload_off", "OFF")

        # Handle entity category update
        entity_category_str = config.get("entity_category")
        if entity_category_str:
            try:
                self._attr_entity_category = EntityCategory(entity_category_str)
            except ValueError:
                _LOGGER.warning(
                    "Invalid entity_category '%s' for binary sensor %s",
                    entity_category_str,
                    self.unique_id,
                )
        else:
            self._attr_entity_category = None

        # Update template if provided
        if self._value_template:
            try:
                self._template = Template(self._value_template, self._manager.hass)
            except Exception as err:
                _LOGGER.error(
                    "Failed to create value template for binary sensor %s: %s",
                    self.unique_id,
                    err,
                )
                self._template = None
        else:
            self._template = None

        # Update device info
        self._device_info_raw = config.get("device")
