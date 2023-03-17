"""Support for Nexia switches."""
from __future__ import annotations

from typing import Any

from nexia.const import OPERATION_MODE_OFF
from nexia.home import NexiaHome
from nexia.thermostat import NexiaThermostat
from nexia.zone import NexiaThermostatZone

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NexiaDataUpdateCoordinator
from .entity import NexiaThermostatZoneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for a Nexia device."""
    coordinator: NexiaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    nexia_home: NexiaHome = coordinator.nexia_home
    entities: list[NexiaHoldSwitch] = []
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat: NexiaThermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        for zone_id in thermostat.get_zone_ids():
            zone: NexiaThermostatZone = thermostat.get_zone_by_id(zone_id)
            entities.append(NexiaHoldSwitch(coordinator, zone))

    async_add_entities(entities)


class NexiaHoldSwitch(NexiaThermostatZoneEntity, SwitchEntity):
    """Provides Nexia hold switch support."""

    def __init__(
        self, coordinator: NexiaDataUpdateCoordinator, zone: NexiaThermostatZone
    ) -> None:
        """Initialize the hold mode switch."""
        switch_name = f"{zone.get_name()} Hold"
        zone_id = zone.zone_id
        super().__init__(coordinator, zone, name=switch_name, unique_id=zone_id)

    @property
    def is_on(self) -> bool:
        """Return if the zone is in hold mode."""
        return self._zone.is_in_permanent_hold()

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:timer-off" if self._zone.is_in_permanent_hold() else "mdi:timer"

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
