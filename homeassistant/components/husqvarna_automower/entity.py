"""Platform for Husqvarna Automower base entity."""

import logging

from aioautomower.model import MowerAttributes

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AutomowerDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AutomowerBaseEntity(CoordinatorEntity[AutomowerDataUpdateCoordinator]):
    """Defining the Automower base Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Initialize AutomowerEntity."""
        super().__init__(coordinator)
        self.mower_id = mower_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mower_id)},
            manufacturer="Husqvarna",
            model=self.mower_attributes.system.model,
            name=self.mower_attributes.system.name,
            serial_number=self.mower_attributes.system.serial_number,
            suggested_area="Garden",
        )

    @property
    def mower_attributes(self) -> MowerAttributes:
        """Get the mower attributes of the current mower."""
        return self.coordinator.data[self.mower_id]


class AutomowerControlEntity(AutomowerBaseEntity):
    """AutomowerControlEntity, for dynamic availability."""

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available and self.mower_attributes.metadata.connected
