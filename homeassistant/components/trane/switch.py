"""Switch platform for the Trane Local integration."""

from __future__ import annotations

from typing import Any

from steamloop import HoldType, ThermostatConnection

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import TraneZoneEntity
from .types import TraneConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TraneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Trane Local switch entities."""
    conn = config_entry.runtime_data
    async_add_entities(
        TraneHoldSwitch(conn, config_entry.entry_id, zone_id)
        for zone_id in conn.state.zones
    )


class TraneHoldSwitch(TraneZoneEntity, SwitchEntity):
    """Switch to control the hold mode of a thermostat zone."""

    _attr_translation_key = "hold"

    def __init__(self, conn: ThermostatConnection, entry_id: str, zone_id: str) -> None:
        """Initialize the hold switch."""
        super().__init__(conn, entry_id, zone_id, "hold")

    @property
    def is_on(self) -> bool:
        """Return true if the zone is in permanent hold."""
        return self._zone.hold_type == HoldType.MANUAL

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable permanent hold."""
        self._conn.set_temperature_setpoint(self._zone_id, hold_type=HoldType.MANUAL)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Return to schedule."""
        self._conn.set_temperature_setpoint(self._zone_id, hold_type=HoldType.SCHEDULE)
