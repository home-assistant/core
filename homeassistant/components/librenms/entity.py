"""Base entities for the LibreNMS integration."""

from typing import override

from aiolibrenms.devices.models import LibrenmsDeviceInfo

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LibrenmsCentralDataUpdateCoordinator


class LibrenmsDeviceEntity(CoordinatorEntity[LibrenmsCentralDataUpdateCoordinator]):
    """Define LibreNMS device base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LibrenmsCentralDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_{self.device_id}")
            }
        )

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.device_id in self.coordinator.data.devices

    @property
    def _data(self) -> LibrenmsDeviceInfo:
        """Get DeviceInfo from coordinator."""
        return self.coordinator.data.devices[self.device_id]


class LibrenmsSystemEntity(CoordinatorEntity[LibrenmsCentralDataUpdateCoordinator]):
    """Define LibreNMS base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LibrenmsCentralDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="LibreNMS",
            sw_version=coordinator.data.system.local_ver,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.configuration_url,
            name="LibreNMS",
        )
