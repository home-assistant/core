"""Support for Sure PetCare Flaps/Pets binary sensors."""
from __future__ import annotations

from typing import cast

from surepy.entities import SurepyEntity
from surepy.entities.pet import Pet as SurepyPet
from surepy.enums import EntityType, Location

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PRESENCE,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SurePetcareDataCoordinator
from .const import DOMAIN
from .entity import SurePetcareEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sure PetCare Flaps binary sensors based on a config entry."""

    entities: list[SurePetcareBinarySensor] = []

    coordinator: SurePetcareDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    for surepy_entity in coordinator.data.values():

        # connectivity
        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(DeviceConnectivity(surepy_entity.id, coordinator))
        elif surepy_entity.type == EntityType.PET:
            entities.append(Pet(surepy_entity.id, coordinator))
        elif surepy_entity.type == EntityType.HUB:
            entities.append(Hub(surepy_entity.id, coordinator))

    async_add_entities(entities)


class SurePetcareBinarySensor(SurePetcareEntity, BinarySensorEntity):
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(
        self,
        surepetcare_id: int,
        coordinator: SurePetcareDataCoordinator,
    ) -> None:
        """Initialize a Sure Petcare binary sensor."""
        super().__init__(surepetcare_id, coordinator)

        self._attr_name = self._device_name
        self._attr_unique_id = self._device_id


class Hub(SurePetcareBinarySensor):
    """Sure Petcare Hub."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and bool(self._attr_is_on)

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Get the latest data and update the state."""
        state = surepy_entity.raw_data()["status"]
        self._attr_is_on = self._attr_available = bool(state["online"])
        if surepy_entity.raw_data():
            self._attr_extra_state_attributes = {
                "led_mode": int(surepy_entity.raw_data()["status"]["led_mode"]),
                "pairing_mode": bool(
                    surepy_entity.raw_data()["status"]["pairing_mode"]
                ),
            }
        else:
            self._attr_extra_state_attributes = {}


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    _attr_device_class = DEVICE_CLASS_PRESENCE

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Get the latest data and update the state."""
        surepy_entity = cast(SurepyPet, surepy_entity)
        state = surepy_entity.location
        try:
            self._attr_is_on = bool(Location(state.where) == Location.INSIDE)
        except (KeyError, TypeError):
            self._attr_is_on = False
        if state:
            self._attr_extra_state_attributes = {
                "since": state.since,
                "where": state.where,
            }
        else:
            self._attr_extra_state_attributes = {}


class DeviceConnectivity(SurePetcareBinarySensor):
    """Sure Petcare Device."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(
        self,
        surepetcare_id: int,
        coordinator: SurePetcareDataCoordinator,
    ) -> None:
        """Initialize a Sure Petcare Device."""
        super().__init__(surepetcare_id, coordinator)
        self._attr_name = f"{self._device_name} Connectivity"
        self._attr_unique_id = f"{self._device_id}-connectivity"

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        state = surepy_entity.raw_data()["status"]
        self._attr_is_on = bool(state)
        if state:
            self._attr_extra_state_attributes = {
                "device_rssi": f'{state["signal"]["device_rssi"]:.2f}',
                "hub_rssi": f'{state["signal"]["hub_rssi"]:.2f}',
            }
        else:
            self._attr_extra_state_attributes = {}
