"""Sensor platform for Victron Energy integration."""

from __future__ import annotations

import logging
from typing import Any

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

    def handle_mqtt_message(self, topic: str, payload: bytes) -> None:
        """Handle incoming MQTT message for this sensor."""
        value = self._parse_payload(payload)
        if value in ("unknown", "None", "null", "", "unavailable", "disconnected") or (
            isinstance(value, str)
            and value.lower() in ("none", "null", "n/a", "na", "unavailable")
        ):
            value = None

        if self._attr_native_unit_of_measurement and value is not None:
            try:
                value = float(value)
            except (ValueError, TypeError):
                _LOGGER.exception(
                    "Failed to convert sensor value to float, setting to None"
                )
                value = None
        _LOGGER.debug(
            "Setting state for %s to %s (type: %s)", self._attr_name, value, type(value)
        )
        self._attr_native_value = value
        self.schedule_update_ha_state()
