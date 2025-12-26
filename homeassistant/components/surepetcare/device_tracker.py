"""Support for Sure PetCare pet device tracking."""

from __future__ import annotations

from typing import cast

from surepy.entities import SurepyEntity
from surepy.entities.pet import Pet as SurepyPet
from surepy.enums import EntityType, Location

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SurePetcareDataCoordinator
from .entity import SurePetcareEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sure PetCare device tracker entities based on a config entry."""
    coordinator: SurePetcareDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SurePetcareDeviceTracker] = [
        SurePetcareDeviceTracker(surepy_entity.id, coordinator)
        for surepy_entity in coordinator.data.values()
        if surepy_entity.type == EntityType.PET
    ]

    async_add_entities(entities)


class SurePetcareDeviceTracker(SurePetcareEntity, TrackerEntity):
    """Sure Petcare pet device tracker."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        surepetcare_id: int,
        coordinator: SurePetcareDataCoordinator,
    ) -> None:
        """Initialize the pet device tracker."""
        super().__init__(surepetcare_id, coordinator)
        self._attr_unique_id = f"{self._device_id}-tracker"

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Update the tracker attributes from the Sure Pet entity."""
        surepy_entity = cast(SurepyPet, surepy_entity)
        state = surepy_entity.location

        try:
            location = Location(state.where)
            if location == Location.INSIDE:
                self._attr_location_name = STATE_HOME
            elif location == Location.OUTSIDE:
                self._attr_location_name = STATE_NOT_HOME
            else:
                self._attr_location_name = None

            self._attr_extra_state_attributes = {
                "since": state.since,
            }
        except ValueError:
            self._attr_extra_state_attributes = {
                "since": None,
            }
            self._attr_location_name = None
