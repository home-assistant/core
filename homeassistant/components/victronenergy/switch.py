"""Switch platform for Victron Energy integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Victron Energy switches from a config entry."""
    manager = hass.data[DOMAIN][entry.entry_id]
    manager.set_platform_add_entities("switch", async_add_entities)


class MQTTDiscoveredSwitch(VictronBaseEntity, SwitchEntity):
    """Representation of a discovered MQTT switch."""

    _command_topic: str | None
    _payload_on: str
    _payload_off: str
    _state_on: str
    _state_off: str

    def _parse_config(self, config: dict[str, Any]) -> None:
        """Parse configuration fields from the config dictionary."""
        self._command_topic = config.get("command_topic")
        self._payload_on = config.get("payload_on", "ON")
        self._payload_off = config.get("payload_off", "OFF")
        self._state_on = config.get("state_on", "ON")
        self._state_off = config.get("state_off", "OFF")

    def __init__(
        self,
        manager,
        device_key: DeviceKey,
        device_info: dict[str, Any],
        unique_id: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(manager, device_key, device_info, unique_id, config)
        self._parse_config(config)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update the switch configuration."""
        super().update_config(config)
        self._parse_config(config)

    def handle_mqtt_message(self, topic: str, payload: bytes) -> None:
        """Handle incoming MQTT message for this switch."""
        value = self._parse_payload(payload)
        # Determine switch state based on payload
        if value == self._state_on:
            self._attr_is_on = True
        elif value == self._state_off:
            self._attr_is_on = False
        elif str(value).lower() in ("true", "1", "on", "yes"):
            self._attr_is_on = True
        elif str(value).lower() in ("false", "0", "off", "no"):
            self._attr_is_on = False
        else:
            _LOGGER.warning("Unknown switch state value: %s", value)
            self._attr_is_on = None

        _LOGGER.debug(
            "Setting switch state for %s to %s (from value: %s)",
            self._attr_name,
            self._attr_is_on,
            value,
        )
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if not self._command_topic:
            return

        _LOGGER.debug(
            "Turning on switch %s by publishing %s to %s",
            self._attr_name,
            self._payload_on,
            self._command_topic,
        )
        self._manager.publish(self._command_topic, self._payload_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if not self._command_topic:
            return

        _LOGGER.debug(
            "Turning off switch %s by publishing %s to %s",
            self._attr_name,
            self._payload_off,
            self._command_topic,
        )
        self._manager.publish(self._command_topic, self._payload_off)
