"""Platform for Husqvarna Automower base entity."""

import logging

from aioautomower.model import MowerActivities, MowerAttributes, MowerStates

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AutomowerDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ERROR_ACTIVITIES = (
    MowerActivities.STOPPED_IN_GARDEN,
    MowerActivities.UNKNOWN,
    MowerActivities.NOT_APPLICABLE,
)
ERROR_STATES = [
    MowerStates.FATAL_ERROR,
    MowerStates.ERROR,
    MowerStates.ERROR_AT_POWER_UP,
    MowerStates.NOT_APPLICABLE,
    MowerStates.UNKNOWN,
    MowerStates.STOPPED,
    MowerStates.OFF,
]


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


class AutomowerAvailableEntity(AutomowerBaseEntity):
    """Replies available when the mower is connected."""

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available and self.mower_attributes.metadata.connected


class AutomowerControlEntity(AutomowerAvailableEntity):
    """Replies available when the mower is connected and not in error state."""

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available and (
            self.mower_attributes.mower.state not in ERROR_STATES
            or self.mower_attributes.mower.activity not in ERROR_ACTIVITIES
        )
