"""The Modern Forms integration."""

from typing import override

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModernFormsDataUpdateCoordinator

_NAME_SEPARATORS = " -_"


def strip_device_name_prefix(device_name: str, name: str) -> str | None:
    """Strip a leading device-name prefix so has_entity_name doesn't duplicate it.

    Returns None (rather than a name identical to the device name) when
    the fixture name adds nothing beyond the device name.
    """
    if not device_name or not name.lower().startswith(device_name.lower()):
        return name
    rest = name[len(device_name) :]
    if rest and rest[0] not in _NAME_SEPARATORS:
        return name
    return rest.lstrip(_NAME_SEPARATORS) or None


class ModernFormsDeviceEntity(CoordinatorEntity[ModernFormsDataUpdateCoordinator]):
    """Defines a Modern Forms device entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: ModernFormsDataUpdateCoordinator,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the Modern Forms entity."""
        super().__init__(coordinator)
        self._attr_enabled_default = enabled_default
        self._entry_id = entry_id

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information about this Modern Forms device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.info.mac_address)},
            connections={
                (CONNECTION_NETWORK_MAC, self.coordinator.data.info.mac_address)
            },
            name=self.coordinator.data.info.device_name,
            manufacturer="Modern Forms",
            model=self.coordinator.data.info.fan_type,
            sw_version=(
                f"{self.coordinator.data.info.firmware_version} /"
                f" {self.coordinator.data.info.main_mcu_firmware_version}"
            ),
        )
