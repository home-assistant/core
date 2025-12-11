"""Binary sensor platform for Victron Energy integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from paho.mqtt.client import MQTTMessage

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

    def handle_mqtt_message(self, msg: MQTTMessage) -> None:
        """Handle new MQTT message."""
        try:
            payload = msg.payload.decode()

            # Handle empty payload immediately - set entity to unknown
            if not payload.strip():
                self._attr_is_on = None
                self.schedule_update_ha_state()
                return

            if self._value_template:
                # Use template to process the payload
                try:
                    processed_value = (
                        self._value_template.async_render_with_possible_json_value(
                            payload
                        )
                    )
                except Exception:
                    _LOGGER.warning(
                        "Template error for binary sensor %s",
                        self.unique_id,
                        exc_info=True,
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
        except Exception:
            _LOGGER.exception(
                "Error handling MQTT message for binary sensor %s",
                self.unique_id,
            )
