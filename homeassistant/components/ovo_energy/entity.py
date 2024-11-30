"""Support for OVO Energy."""

from __future__ import annotations

from ovoenergy import OVOEnergy
from ovoenergy.models import OVODailyUsage

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class OVOEnergyEntity(CoordinatorEntity[DataUpdateCoordinator[OVODailyUsage]]):
    """Defines a base OVO Energy entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[OVODailyUsage],
        client: OVOEnergy,
    ) -> None:
        """Initialize the OVO Energy entity."""
        super().__init__(coordinator)
        self._client = client


class OVOEnergyDeviceEntity(OVOEnergyEntity):
    """Defines a OVO Energy device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this OVO Energy instance."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._client.account_id)},
            manufacturer="OVO Energy",
            name=self._client.username,
        )
