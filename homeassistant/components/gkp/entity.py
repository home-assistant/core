"""Base entity for GKP integration."""

from typing import override

from gkphomepython import Thermostat

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GkpDeviceCoordinator


class GkpEntity(CoordinatorEntity[GkpDeviceCoordinator]):
    """Base entity for GKP devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GkpDeviceCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        thermostat = coordinator.data.thermostat
        self.device_id = thermostat.device_id
        self._attr_unique_id = thermostat.device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, thermostat.device_id)},
            name=thermostat.room_name,
            manufacturer="GKP",
            model=thermostat.device_type,
            sw_version=thermostat.firmware_version,
        )

    @property
    def thermostat(self) -> Thermostat:
        """Return the thermostat from the coordinator data."""
        return self.coordinator.data.thermostat

    @property
    @override
    def available(self) -> bool:
        """Return True if the device reported recently."""
        return super().available and self.thermostat.is_online(
            dt_util.utcnow(), self.coordinator.hub_coordinator.first_wake_up
        )
