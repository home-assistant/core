"""Timetable select for the Tado integration."""

from typing import Any

from PyTado.interface.api.my_tado import Timetable

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TadoConfigEntry, TadoDataUpdateCoordinator, entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado select platform."""

    tado = entry.runtime_data.coordinator
    entities: list[TadoZoneTimetableSelectEntity] = [
        TadoZoneTimetableSelectEntity(
            tado, zone["name"], zone["id"], zone["devices"][0]
        )
        for zone in tado.zones
    ]
    async_add_entities(entities, True)


class TadoZoneTimetableSelectEntity(entity.TadoZoneEntity, SelectEntity):
    """Selection of timetable for Tado zone."""

    _attr_translation_key = "timetable"

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        zone_name: str,
        zone_id: int,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the Tado zone timetable select entity."""
        super().__init__(zone_name, coordinator.home_id, zone_id, coordinator)

        self._device_info = device_info
        self._device_id = self._device_info["shortSerialNo"]
        self._attr_unique_id = f"{zone_id} {coordinator.home_id} timetable"

        self._attr_options = [t.name.lower() for t in Timetable]
        self._attr_current_option = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_current_option is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        timetables = self.coordinator.data.get("timetable")
        timetable = timetables.get(self.zone_id) if timetables is not None else None
        if timetable is not None:
            self._attr_current_option = timetable.name.lower()
        else:
            self._attr_current_option = None
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Send updated value to Tado server."""
        timetable = Timetable[option.upper()]
        self._attr_current_option = option
        self.async_write_ha_state()
        await self.coordinator.set_timetable(self.zone_id, timetable)
        await self.coordinator.async_request_refresh()
