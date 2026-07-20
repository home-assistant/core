"""Base entities for the LibreNMS integration."""

from aiolibrenms.devices.models import LibrenmsDeviceInfo

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LibrenmsDataUpdateCoordinator


class LibrenmsDeviceEntity(CoordinatorEntity[LibrenmsDataUpdateCoordinator]):
    """Define LibreNMS device base entity."""

    _attr_has_entity_name = True
    dev_info: LibrenmsDeviceInfo

    def __init__(
        self,
        coordinator: LibrenmsDataUpdateCoordinator,
        dev_info: LibrenmsDeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.dev_info = dev_info

        identifier = f"{coordinator.config_entry.entry_id}_{dev_info.device_id}"
        sw_version = dev_info.version
        model = None
        configuration_url = (
            f"{coordinator.configuration_url}/device/{dev_info.device_id}"
        )
        if dev_info.os != "ping":
            if sw_version and (feature := dev_info.features) is not None:
                sw_version += f" ({feature})"
            model = dev_info.hardware

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            sw_version=sw_version,
            configuration_url=configuration_url,
            name=dev_info.display,
            model=model,
            serial_number=dev_info.serial,
        )


class LibrenmsSystemEntity(CoordinatorEntity[LibrenmsDataUpdateCoordinator]):
    """Define LibreNMS base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LibrenmsDataUpdateCoordinator,
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
