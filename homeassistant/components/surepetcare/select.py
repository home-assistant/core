"""Support for Sure PetCare Pets select entities."""

from __future__ import annotations

from typing import cast

from surepy.entities import SurepyEntity
from surepy.entities.pet import Pet as SurepyPet
from surepy.enums import EntityType, Location

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CREATE_PET_SELECT,
    CONF_FLAPS_MAPPINGS,
    CONF_MANUALLY_SET_LOCATION,
    CONF_PET_SELECT_OPTIONS,
    DOMAIN,
)
from .coordinator import SurePetcareDataCoordinator
from .entity import SurePetcareEntity
from .types import FlapMappings


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sure PetCare Pets select entities based on a config entry."""

    if entry.options.get(CONF_CREATE_PET_SELECT) is False:
        return

    coordinator: SurePetcareDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[PetSelect] = [
        PetSelect(
            surepy_entity.id,
            coordinator,
            entry.options[CONF_PET_SELECT_OPTIONS],
            entry.options[CONF_FLAPS_MAPPINGS],
            entry.options[CONF_MANUALLY_SET_LOCATION],
        )
        for surepy_entity in coordinator.data.values()
        if surepy_entity.type == EntityType.PET
    ]

    async_add_entities(entities)


class PetSelect(SurePetcareEntity, SelectEntity):
    """Sure Petcare Pet select entity representing a pet's location."""

    _flaps_mappings: dict[str, FlapMappings] = {}
    _manually_set_location_mappings: FlapMappings | None = None

    def __init__(
        self,
        surepetcare_id: int,
        coordinator: SurePetcareDataCoordinator,
        options: list[str],
        flaps_mappings: dict[str, FlapMappings],
        manually_set_location_mappings: FlapMappings,
    ) -> None:
        """Initialize a Sure Petcare Pet select."""
        self._attr_options = options
        self._attr_current_option = None
        self._flaps_mappings = flaps_mappings
        self._manually_set_location_mappings = manually_set_location_mappings
        self._attr_extra_state_attributes = {}

        # Calling the SurePetcareEntity constructor last because it will call
        # _update_attr which needs the above attributes to be set.
        super().__init__(surepetcare_id, coordinator)
        self._attr_name = self._device_name
        self._attr_unique_id = self._device_id

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Get the latest data and update the state."""
        surepy_entity = cast(SurepyPet, surepy_entity)

        position = surepy_entity._data.get("position", {})  # noqa: SLF001
        device_id = position.get("device_id")
        device_id_str = str(device_id) if device_id is not None else None
        user_id = position.get("user_id")
        user_id_str = str(user_id) if user_id is not None else None

        location = surepy_entity.location

        state_attr = self._attr_extra_state_attributes
        # If the pet location has not changed and the last update was manual,
        # don't update the state.
        if (
            state_attr.get("last_update_type") == "manual"
            and location.since == state_attr.get("since")
            and location.where == state_attr.get("where")
            and device_id_str == state_attr.get("last_seen_device_id")
        ):
            return

        self._attr_current_option = self._get_pet_location_zone(
            device_id_str, user_id_str, Location(location.where)
        )
        self._attr_extra_state_attributes = {
            "since": location.since,
            "where": location.where,
            "last_seen_device_id": device_id_str,
            "last_update_type": "auto",
        }

    def _get_pet_location_zone(
        self, device_id: str | None, user_id: str | None, location: Location
    ) -> str:
        """Get the pet location zone."""
        mappings = None
        if device_id is None and user_id is not None:
            mappings = self._manually_set_location_mappings
        elif device_id is not None:
            mappings = self._flaps_mappings.get(device_id)

        location_zone = "unknown"
        if mappings is not None:
            if location == Location.INSIDE:
                location_zone = mappings["entry"]
            elif location == Location.OUTSIDE:
                location_zone = mappings["exit"]

        return location_zone

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self._attr_options:
            raise ValueError(f"Invalid option for {self.entity_id}: {option}")

        self._attr_current_option = option
        self._attr_extra_state_attributes["last_update_type"] = "manual"
        self.async_write_ha_state()
