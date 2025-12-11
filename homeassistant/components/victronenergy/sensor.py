"""Sensor platform for Victron Energy integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from paho.mqtt.client import MQTTMessage

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import VictronBaseEntity
from .types import DeviceKey

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Energy sensors from a config entry."""
    manager = hass.data[DOMAIN][entry.entry_id]
    manager.set_platform_add_entities("sensor", async_add_entities)


class MQTTDiscoveredSensor(VictronBaseEntity, SensorEntity):
    """Representation of a discovered MQTT sensor."""

    def _parse_config(self, config: dict[str, Any]) -> None:
        """Parse configuration fields from the config dictionary."""
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        self._attr_state_class = config.get("state_class")
        self._attr_suggested_display_precision = config.get(
            "suggested_display_precision"
        )

    def __init__(
        self,
        manager,
        device_key: DeviceKey,
        device_info: dict[str, Any],
        unique_id: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(manager, device_key, device_info, unique_id, config)
        self._parse_config(config)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update the sensor configuration."""
        super().update_config(config)
        self._parse_config(config)

    def handle_mqtt_message(self, msg: MQTTMessage) -> None:
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
        except json.JSONDecodeError:
            _LOGGER.debug("Failed to decode sensor message JSON", exc_info=True)
            json_payload = None

        if self._value_template:
            try:
                value = self._value_template.async_render_with_possible_json_value(
                    payload, None
                )
            except (TypeError, ValueError):
                _LOGGER.debug("Failed to render value_template", exc_info=True)
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
