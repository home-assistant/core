"""Common code for GogoGate2 component."""

from __future__ import annotations

from ismartgate.common import AbstractDoor, get_door_by_id

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import DeviceDataUpdateCoordinator


class GoGoGate2Entity(CoordinatorEntity[DeviceDataUpdateCoordinator]):
    """Base class for gogogate2 entities."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        data_update_coordinator: DeviceDataUpdateCoordinator,
        door: AbstractDoor,
        unique_id: str,
    ) -> None:
        """Initialize gogogate2 base entity."""
        super().__init__(data_update_coordinator)
        self._config_entry = config_entry
        self._door = door
        self._door_id = door.door_id
        self._api = data_update_coordinator.api
        self._attr_unique_id = unique_id

    @property
    def door(self) -> AbstractDoor:
        """Return the door object."""
        door = get_door_by_id(self._door.door_id, self.coordinator.data)
        self._door = door or self._door
        return self._door

    @property
    def door_status(self) -> AbstractDoor:
        """Return the door with status."""
        data = self.coordinator.data
        door_with_statuses = self._api.async_get_door_statuses_from_info(data)
        return door_with_statuses[self._door_id]

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for the controller."""
        data = self.coordinator.data
        if data.remoteaccessenabled:
            configuration_url = f"https://{data.remoteaccess}"
        else:
            configuration_url = f"http://{self._config_entry.data[CONF_IP_ADDRESS]}"
        return DeviceInfo(
            configuration_url=configuration_url,
            identifiers={(DOMAIN, str(self._config_entry.unique_id))},
            name=self._config_entry.title,
            manufacturer=MANUFACTURER,
            model=data.model,
            sw_version=data.firmwareversion,
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"door_id": self._door_id}
