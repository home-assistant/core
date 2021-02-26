"""Support for Gogogate2 garage Doors."""
from typing import Callable, List, Optional

from gogogate2_api.common import AbstractDoor, get_configured_doors, get_door_by_id

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_BATTERY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import (
    DeviceDataUpdateCoordinator,
    cover_unique_id,
    get_data_update_coordinator,
)
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the config entry."""
    data_update_coordinator = get_data_update_coordinator(hass, config_entry)

    async_add_entities(
        [
            DoorSensor(config_entry, data_update_coordinator, door)
            for door in get_configured_doors(data_update_coordinator.data)
            if door.sensorid and door.sensorid != "WIRE"
        ]
    )


class DoorSensor(CoordinatorEntity):
    """Sensor entity for goggate2."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        data_update_coordinator: DeviceDataUpdateCoordinator,
        door: AbstractDoor,
    ) -> None:
        """Initialize the object."""
        super().__init__(data_update_coordinator)
        self._config_entry = config_entry
        self._door = door
        self._api = data_update_coordinator.api
        self._unique_id = cover_unique_id(config_entry, door)
        self._is_available = True

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the door."""
        return f"{self._get_door().name} battery"

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self):
        """Return the state of the entity."""
        door = self._get_door()
        return door.voltage

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = super().state_attributes or {}
        door = self._get_door()
        if door.sensorid is not None:
            attrs["sensorid"] = door.door_id
        return attrs

    def _get_door(self) -> AbstractDoor:
        door = get_door_by_id(self._door.door_id, self.coordinator.data)
        self._door = door or self._door
        return self._door

    @property
    def device_info(self):
        """Device info for the controller, details are set by the cover entity."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.unique_id)},
        }
