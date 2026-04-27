"""Binary sensors for LocknAlert zones."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import LocknAlertConfigEntry
from .const import CONF_BRIDGE_SERIAL
from .entity import LocknAlertEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LocknAlertConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    bridge_serial = str(entry.data[CONF_BRIDGE_SERIAL])

    @callback
    def _sync_entities() -> None:
        entities = [
            LocknAlertZoneBinarySensor(bridge_serial, zone_id, zone, coordinator.state.available)
            for zone_id, zone in coordinator.state.zones.items()
        ]
        if entities:
            async_add_entities(entities)

    coordinator.async_listen("*", _sync_entities)
    _sync_entities()


class LocknAlertZoneBinarySensor(LocknAlertEntity, BinarySensorEntity):
    def __init__(self, bridge_id: str, zone_id: str, zone: dict, available: bool) -> None:
        super().__init__(bridge_id, f"zone_{zone_id}")
        self._zone = zone
        self._available = available
        self._attr_name = zone.get("name", f"Zone {zone_id}")

    @property
    def is_on(self) -> bool:
        return bool(self._zone.get("open", self._zone.get("state") == "open"))
