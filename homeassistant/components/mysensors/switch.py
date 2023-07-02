"""Support for MySensors switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import setup_mysensors_platform
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo, SensorType
from .device import MySensorsEntity
from .helpers import on_unload


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""
    device_class_map: dict[SensorType, type[MySensorsSwitch]] = {
        "S_DOOR": MySensorsSwitch,
        "S_MOTION": MySensorsSwitch,
        "S_SMOKE": MySensorsSwitch,
        "S_LIGHT": MySensorsSwitch,
        "S_LOCK": MySensorsSwitch,
        "S_BINARY": MySensorsSwitch,
        "S_SPRINKLER": MySensorsSwitch,
        "S_WATER_LEAK": MySensorsSwitch,
        "S_SOUND": MySensorsSwitch,
        "S_VIBRATION": MySensorsSwitch,
        "S_MOISTURE": MySensorsSwitch,
        "S_WATER_QUALITY": MySensorsSwitch,
    }

    async def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors switch."""
        setup_mysensors_platform(
            hass,
            Platform.SWITCH,
            discovery_info,
            device_class_map,
            async_add_entities=async_add_entities,
        )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.SWITCH),
            async_discover,
        ),
    )


class MySensorsSwitch(MySensorsEntity, SwitchEntity):
    """Representation of the value of a MySensors Switch child node."""

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return self._values.get(self.value_type) == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 1, ack=1
        )
        if self.assumed_state:
            # Optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_ON
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 0, ack=1
        )
        if self.assumed_state:
            # Optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_OFF
            self.async_write_ha_state()
