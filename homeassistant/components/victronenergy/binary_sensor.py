"""Binary sensor platform for Victron Energy integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up Victron Energy binary sensors from a config entry."""
    manager = hass.data[DOMAIN][entry.entry_id]
    manager.set_platform_add_entities("binary_sensor", async_add_entities)


class MQTTDiscoveredBinarySensor(VictronBaseEntity, BinarySensorEntity):
    """Representation of a discovered MQTT binary sensor."""

    _payload_on: str
    _payload_off: str

    def _parse_config(self, config: dict[str, Any]) -> None:
        """Parse configuration fields from the config dictionary."""
        self._payload_on = config.get("payload_on", "ON")
        self._payload_off = config.get("payload_off", "OFF")

    def __init__(
        self,
        manager,
        device_key: DeviceKey,
        device_info: dict[str, Any],
        unique_id: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(manager, device_key, device_info, unique_id, config)
        self._parse_config(config)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update the binary sensor configuration."""
        super().update_config(config)
        self._parse_config(config)

    def handle_mqtt_message(self, topic: str, payload: bytes) -> None:
        """Handle new MQTT message."""
        value = self._parse_payload(payload)
        if value == self._payload_on:
            self._attr_is_on = True
        elif value == self._payload_off:
            self._attr_is_on = False
        elif isinstance(value, bool):
            self._attr_is_on = value
        elif isinstance(value, (int, float)):
            self._attr_is_on = bool(value)
        else:
            _LOGGER.warning("Unknown binary_sensor state value: %s", value)
            self._attr_is_on = None

        _LOGGER.debug(
            "Binary sensor %s updated to: %s (from payload: %s)",
            self.unique_id,
            self._attr_is_on,
            payload,
        )
        self.schedule_update_ha_state()
