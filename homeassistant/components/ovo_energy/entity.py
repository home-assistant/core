"""Support for OVO Energy."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OVOEnergyDataUpdateCoordinator


class OVOEnergyEntity(CoordinatorEntity[OVOEnergyDataUpdateCoordinator]):
    """Defines a base OVO Energy entity."""

    _attr_has_entity_name = True


class OVOEnergyDeviceEntity(OVOEnergyEntity):
    """Defines a OVO Energy device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this OVO Energy instance."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.coordinator.client.account_id)},
            manufacturer="OVO Energy",
            name=self.coordinator.client.username,
        )
