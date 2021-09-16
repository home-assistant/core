"""Support for Sure PetCare Flaps/Pets binary sensors."""
from __future__ import annotations

from abc import abstractmethod
import logging

from surepy.entities import SurepyEntity
from surepy.enums import EntityType, Location

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PRESENCE,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Sure PetCare Flaps binary sensors based on a config entry."""

    entities: list[SurepyEntity | Pet | Hub | DeviceConnectivity] = []

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

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


class SurePetcareBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(
        self,
        _id: int,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize a Sure Petcare binary sensor."""
        super().__init__(coordinator)

        self._id = _id

        surepy_entity: SurepyEntity = coordinator.data[_id]

        # cover special case where a device has no name set
        if surepy_entity.name:
            name = surepy_entity.name
        else:
            name = f"Unnamed {surepy_entity.type.name.capitalize()}"

        self._attr_name = f"{surepy_entity.type.name.capitalize()} {name.capitalize()}"
        self._attr_unique_id = f"{surepy_entity.household_id}-{_id}"
        self._update_attr(coordinator.data[_id])

    @abstractmethod
    @callback
    def _update_attr(self, surepy_entity) -> None:
        """Update the state and attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and update the state."""
        self._update_attr(self.coordinator.data[self._id])
        self.async_write_ha_state()


class Hub(SurePetcareBinarySensor):
    """Sure Petcare Hub."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and bool(self._attr_is_on)

    @callback
    def _update_attr(self, surepy_entity) -> None:
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
        _LOGGER.debug("%s -> state: %s", self.name, state)


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    _attr_device_class = DEVICE_CLASS_PRESENCE

    @callback
    def _update_attr(self, surepy_entity) -> None:
        """Get the latest data and update the state."""
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
        _LOGGER.debug("%s -> state: %s", self.name, state)


class DeviceConnectivity(SurePetcareBinarySensor):
    """Sure Petcare Device."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(
        self,
        _id: int,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize a Sure Petcare Device."""
        super().__init__(_id, coordinator)
        self._attr_name = f"{self.name}_connectivity"
        self._attr_unique_id = (
            f"{self.coordinator.data[self._id].household_id}-{self._id}-connectivity"
        )

    @callback
    def _update_attr(self, surepy_entity):
        state = surepy_entity.raw_data()["status"]
        self._attr_is_on = bool(state)
        if state:
            self._attr_extra_state_attributes = {
                "device_rssi": f'{state["signal"]["device_rssi"]:.2f}',
                "hub_rssi": f'{state["signal"]["hub_rssi"]:.2f}',
            }
        else:
            self._attr_extra_state_attributes = {}
        _LOGGER.debug("%s -> state: %s", self.name, state)
