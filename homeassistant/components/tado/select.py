"""Timetable select for the Tado integration."""

from typing import override

from PyTado.interface.api.my_tado import Timetable

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import entity
from .coordinator import TadoConfigEntry, TadoDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado select platform."""

    tado = entry.runtime_data
    entities: list[TadoZoneTimetableSelectEntity] = [
        TadoZoneTimetableSelectEntity(tado, zone["name"], zone["id"])
        for zone in tado.zones
    ]
    async_add_entities(entities)


class TadoZoneTimetableSelectEntity(entity.TadoZoneEntity, SelectEntity):
    """Selection of timetable for Tado zone."""

    _attr_translation_key = "timetable"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        zone_name: str,
        zone_id: int,
    ) -> None:
        """Initialize the Tado zone timetable select entity."""
        super().__init__(zone_name, coordinator.home_id, zone_id, coordinator)

        self._attr_unique_id = f"{zone_id} {coordinator.home_id} timetable"

        self._attr_options = [t.name.lower() for t in Timetable]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently active timetable for the zone."""
        timetable = self.coordinator.data["timetable"].get(self.zone_id)
        return timetable.name.lower() if timetable is not None else None

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.current_option is not None

    @override
    async def async_select_option(self, option: str) -> None:
        """Send updated value to Tado server."""
        await self.coordinator.set_timetable(self.zone_id, Timetable[option.upper()])
        self.async_write_ha_state()
