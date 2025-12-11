"""Sensor platform for Victron Energy integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import StateType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Energy sensors from a config entry."""
    manager = hass.data[DOMAIN][entry.entry_id]
    manager.set_sensor_add_entities(async_add_entities)


class MQTTDiscoveredSensor(SensorEntity):
    """Representation of a discovered MQTT sensor."""

    def __init__(self, config: dict[str, Any], unique_id: str, manager) -> None:
        """Initialize the sensor."""
        self._manager = manager
        self._attr_name = config.get("name")
        self._state_topic = config.get("state_topic")
        self._value_template = config.get("value_template")
        self._attr_unique_id = unique_id
        self._desired_entity_id = f"sensor.{unique_id}"
        self._attr_entity_id = f"sensor.{unique_id}"
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        self._attr_icon = config.get("icon")
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class")
        self._attr_enabled_by_default = config.get("enabled_by_default", True)
        self._attr_suggested_display_precision = config.get(
            "suggested_display_precision"
        )

        # Set entity category for diagnostic entities
        entity_category = config.get("entity_category")
        if entity_category == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            self._attr_entity_category = None

        self._attr_native_value: Any = None
        self._device_info_raw = config.get("device")

        _LOGGER.debug("MQTTDiscoveredSensor config: %s", config)

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
        """Return the unique ID for this entity."""
        return self._attr_unique_id or ""

    @property
    def should_poll(self) -> bool:
        """Return False as this entity is updated via MQTT messages."""
        return False

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class for the entity."""
        if self._attr_device_class:
            try:
                return SensorDeviceClass(self._attr_device_class)
            except ValueError:
                return None
        return None

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topic and set entity_id when the entity is added to Home Assistant."""
        manager = self._manager
        _LOGGER.debug(
            "Registering entity for topic %s (id: %s)", self._state_topic, id(self)
        )
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
        """Update the sensor configuration."""
        self._attr_name = config.get("name", self._attr_name)
        self._value_template = config.get("value_template")
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        self._attr_icon = config.get("icon")
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class")
        self._attr_enabled_by_default = config.get("enabled_by_default", True)
        self._attr_suggested_display_precision = config.get(
            "suggested_display_precision"
        )

        # Update entity category
        entity_category = config.get("entity_category")
        if entity_category == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            self._attr_entity_category = None

        _LOGGER.debug("Updated sensor config for %s: %s", self._attr_name, config)

    def handle_mqtt_message(self, msg) -> None:
        """Handle incoming MQTT message for this sensor."""
        payload = msg.payload.decode()
        _LOGGER.debug(
            "Received MQTT message for %s (id: %s): %s",
            self._attr_name,
            id(self),
            payload,
        )

        # Handle empty payload immediately - set entity to unknown
        if not payload.strip():
            self._attr_native_value = None
            self.schedule_update_ha_state()
            return

        value = None
        try:
            json_payload = json.loads(payload)
        except json.JSONDecodeError as err:
            _LOGGER.debug("Failed to decode sensor message JSON: %s", err)
            json_payload = None

        if self._value_template:
            template = Template(self._value_template, self.hass)
            try:
                value = template.async_render_with_possible_json_value(payload, None)
            except (TypeError, ValueError) as err:
                _LOGGER.debug("Failed to render value_template: %s", err)
                value = payload
        elif json_payload is not None and "value" in json_payload:
            value = json_payload["value"]
        else:
            value = payload

        # Handle disconnected/invalid states (including template result of None)
        if value is None:
            value = None
        elif value in ("unknown", "None", "null", "", "unavailable", "disconnected"):
            value = None
        elif isinstance(value, str) and value.lower() in (
            "none",
            "null",
            "n/a",
            "na",
            "unavailable",
        ):
            value = None

        # Try to cast to float if the unit is set (for measurements)
        if self._attr_native_unit_of_measurement and value is not None:
            try:
                value = float(value)
            except (ValueError, TypeError):
                _LOGGER.debug(
                    "Failed to convert sensor value to float: %s, setting to None",
                    value,
                )
                value = None

        _LOGGER.debug(
            "Setting state for %s to %s (type: %s)", self._attr_name, value, type(value)
        )
        self._attr_native_value = value
        self.schedule_update_ha_state()

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        _LOGGER.debug(
            "native_value for %s is %s (type: %s, id: %s)",
            self._attr_name,
            self._attr_native_value,
            type(self._attr_native_value),
            id(self),
        )
        if (
            self._attr_native_unit_of_measurement
            and self._attr_native_value is not None
        ):
            try:
                return float(self._attr_native_value)
            except (ValueError, TypeError):
                return self._attr_native_value
        return self._attr_native_value
