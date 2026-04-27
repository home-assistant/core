"""Sensors for LocknAlert bridge diagnostics."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import LocknAlertConfigEntry
from .const import CONF_BRIDGE_SERIAL
from .entity import LocknAlertEntity

DIAGNOSTIC_KEYS = ("firmware", "trouble", "battery", "ac_fail", "signal", "temperature", "uptime")


async def async_setup_entry(
    hass: HomeAssistant, entry: LocknAlertConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    bridge_serial = str(entry.data[CONF_BRIDGE_SERIAL])
    bridge = coordinator.state.bridge
    entities = [
        LocknAlertDiagnosticSensor(bridge_serial, key, bridge, coordinator.state.available)
        for key in DIAGNOSTIC_KEYS
    ]
    async_add_entities(entities)


class LocknAlertDiagnosticSensor(LocknAlertEntity, SensorEntity):
    def __init__(self, bridge_id: str, key: str, bridge: dict, available: bool) -> None:
        super().__init__(bridge_id, f"sensor_{key}")
        self._key = key
        self._bridge = bridge
        self._available = available
        self._attr_name = f"Bridge {key.replace('_', ' ').title()}"

    @property
    def native_value(self):
        return self._bridge.get(self._key)
