"""Base entity for the Trane Local integration."""

from __future__ import annotations

from typing import Any

from steamloop import ThermostatConnection, Zone

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER


class TraneEntity(Entity):
    """Base class for all Trane entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, conn: ThermostatConnection) -> None:
        """Initialize the entity."""
        self._conn = conn

    async def async_added_to_hass(self) -> None:
        """Register event callback when added to hass."""
        self.async_on_remove(self._conn.add_event_callback(self._handle_event))

    @callback
    def _handle_event(self, _event: dict[str, Any]) -> None:
        """Handle a thermostat event."""
        self.async_write_ha_state()


class TraneZoneEntity(TraneEntity):
    """Base class for Trane zone-level entities."""

    def __init__(
        self,
        conn: ThermostatConnection,
        entry_id: str,
        zone_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(conn)
        self._zone_id = zone_id
        self._attr_unique_id = f"{entry_id}_{zone_id}_{unique_id_suffix}"
        zone_name = self._zone.name or f"Zone {zone_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{zone_id}")},
            manufacturer=MANUFACTURER,
            name=zone_name,
            suggested_area=zone_name,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def available(self) -> bool:
        """Return True if the zone is available."""
        return self._zone_id in self._conn.state.zones

    @property
    def _zone(self) -> Zone:
        """Return the current zone state."""
        return self._conn.state.zones[self._zone_id]
