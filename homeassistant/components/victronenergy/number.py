"""Number platform for Victron Energy integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.template import Template

from .const import DOMAIN
from .entity import VictronBaseEntity
from .types import DeviceKey

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Energy numbers from a config entry."""
    manager = hass.data[DOMAIN][entry.entry_id]
    manager.set_platform_add_entities("number", async_add_entities)


class MQTTDiscoveredNumber(VictronBaseEntity, NumberEntity):
    """Representation of a discovered MQTT number."""

    _command_topic: str | None
    _command_template: Template | None

    def _parse_config(self, config: dict[str, Any]) -> None:
        mode = config.get("mode", "auto")
        if mode == "box":
            self._attr_mode = NumberMode.BOX
        elif mode == "slider":
            self._attr_mode = NumberMode.SLIDER
        else:
            self._attr_mode = NumberMode.AUTO
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        self._attr_native_min_value = config.get("min", 0)
        self._attr_native_max_value = config.get("max", 100)
        self._attr_native_step = config.get("step", 1)
        self._command_topic = config.get("command_topic")
        command_template = config.get("command_template")
        if command_template:
            try:
                self._command_template = Template(command_template, self._manager.hass)
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Invalid command_template for number %s",
                    self.unique_id,
                    exc_info=True,
                )
                self._command_template = None
        else:
            self._command_template = None

    def __init__(
        self,
        manager,
        device_key: DeviceKey,
        device_info: dict[str, Any],
        unique_id: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize the number."""
        super().__init__(manager, device_key, device_info, unique_id, config)
        self._parse_config(config)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update the number configuration."""
        super().update_config(config)
        self._parse_config(config)

    def handle_mqtt_message(self, topic: str, payload: bytes) -> None:
        """Handle incoming MQTT message for this number entity."""
        value = self._parse_payload(payload)

        # Handle disconnected/invalid states (including template result of None)
        if value in ("unknown", "None", "null", "", "unavailable", "disconnected") or (
            isinstance(value, str)
            and value.lower() in ("none", "null", "n/a", "na", "unavailable")
        ):
            value = None

        # Try to cast to float
        if value is not None:
            try:
                value = float(value)
                # Ensure value is within bounds
                if value < self._attr_native_min_value:
                    value = self._attr_native_min_value
                elif value > self._attr_native_max_value:
                    value = self._attr_native_max_value
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Failed to convert number value to float: %s, setting to None",
                    value,
                )
                value = None

        _LOGGER.debug(
            "Setting number state for %s to %s (type: %s)",
            self._attr_name,
            value,
            type(value),
        )
        self._attr_native_value = value
        self.schedule_update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        if not self._command_topic:
            _LOGGER.warning(
                "No command_topic configured for number %s", self._attr_name
            )
            return

        # Ensure value is within bounds
        value = max(
            self._attr_native_min_value, min(self._attr_native_max_value, value)
        )

        # Apply command template if specified
        payload = str(value)
        if self._command_template:
            try:
                rendered_value = self._command_template.async_render({"value": value})
                # Ensure the rendered value is converted to string for MQTT
                payload = (
                    str(rendered_value) if rendered_value is not None else str(value)
                )
                _LOGGER.debug(
                    "Applied command_template for %s: %s -> %s (type: %s)",
                    self._attr_name,
                    value,
                    payload,
                    type(rendered_value),
                )
            except (TypeError, ValueError):
                _LOGGER.debug(
                    "Failed to render command_template for %s",
                    self._attr_name,
                    exc_info=True,
                )
                payload = str(value)

        _LOGGER.debug(
            "Setting number %s to %s by publishing %s to %s",
            self._attr_name,
            value,
            payload,
            self._command_topic,
        )
        self._manager.publish(self._command_topic, payload)
