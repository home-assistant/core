"""Representation of an SleepIQ device."""

from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class SleepNumberEntity(Entity):
    """Representation of an SleepIQ Entity."""

    def __init__(self, bed):
        """Initialize the SleepIQ Entity."""
        self._bed = bed

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""

        return DeviceInfo(
            identifiers={(DOMAIN, self._bed.id)},
            connections={(device_registry.CONNECTION_NETWORK_MAC, self._bed.mac_addr)},
            manufacturer="SleepNumber",
            name=self._bed.name,
            model=self._bed.model,
        )


class SleepNumberCoordinatorEntity(CoordinatorEntity, SleepNumberEntity):
    """Representation of an SleepIQ Entity with CoordinatorEntity."""

    def __init__(self, bed, status_coordinator=None):
        """Initialize the SleepIQ Entity."""
        super().__init__(status_coordinator)
        self._bed = bed
