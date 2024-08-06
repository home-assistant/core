"""Support for Nexia switches."""

from __future__ import annotations

from typing import Any

from nexia.const import OPERATION_MODE_OFF
from nexia.thermostat import NexiaThermostat
from nexia.zone import NexiaThermostatZone

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NexiaDataUpdateCoordinator
from .entity import NexiaThermostatZoneEntity
from .types import NexiaConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NexiaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for a Nexia device."""
    coordinator = config_entry.runtime_data
    nexia_home = coordinator.nexia_home
    entities: list[NexiaHoldSwitch] = []
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat: NexiaThermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        for zone_id in thermostat.get_zone_ids():
            zone: NexiaThermostatZone = thermostat.get_zone_by_id(zone_id)
            entities.append(NexiaHoldSwitch(coordinator, zone))

    async_add_entities(entities)


class NexiaHoldSwitch(NexiaThermostatZoneEntity, SwitchEntity):
    """Provides Nexia hold switch support."""

    _attr_translation_key = "hold"

    def __init__(
        self, coordinator: NexiaDataUpdateCoordinator, zone: NexiaThermostatZone
    ) -> None:
        """Initialize the hold mode switch."""
        zone_id = zone.zone_id
        super().__init__(coordinator, zone, zone_id)

    @property
    def is_on(self) -> bool:
        """Return if the zone is in hold mode."""
        return self._zone.is_in_permanent_hold()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable permanent hold."""
        if self._zone.get_current_mode() == OPERATION_MODE_OFF:
            await self._zone.call_permanent_off()
        else:
            await self._zone.set_permanent_hold()
        self._signal_zone_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable permanent hold."""
        await self._zone.call_return_to_schedule()
        self._signal_zone_update()
