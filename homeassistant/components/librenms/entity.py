"""Base entity for the LibreNMS integration."""

from typing import override

from aiolibrenms.devices.models import LibrenmsDeviceInfo

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LibrenmsDataUpdateCoordinator


class LibrenmsDeviceEntity(CoordinatorEntity[LibrenmsDataUpdateCoordinator]):
    """Define LibreNMS device base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LibrenmsDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.device_id = device_id

        identifier = f"{coordinator.config_entry.entry_id}_{self.device_id}"
        sw_version = self._data.version
        model = None
        configuration_url = f"{coordinator.configuration_url}/device/{self.device_id}"
        if self._data.os != "ping":
            if sw_version and (feature := self._data.features) is not None:
                sw_version += f" ({feature})"
            model = self._data.hardware

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            sw_version=sw_version,
            configuration_url=configuration_url,
            name=self._data.display,
            model=model,
            serial_number=self._data.serial,
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
