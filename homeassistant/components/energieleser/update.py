"""Firmware update entity for the energieleser integration."""

from typing import override

from energieleser import is_newer_version

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SW_VERSION, device_model_name
from .coordinator import (
    EnergieleserConfigEntry,
    EnergieleserCoordinator,
    EnergieleserFirmwareCoordinator,
)
from .entity import build_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergieleserConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the energieleser firmware update entity."""
    data = entry.runtime_data
    async_add_entities(
        [EnergieleserUpdateEntity(data.firmware_coordinator, data.device_coordinator)]
    )


class EnergieleserUpdateEntity(
    CoordinatorEntity[EnergieleserFirmwareCoordinator], UpdateEntity
):
    """Firmware update entity for an energieleser device."""

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(
        self,
        firmware_coordinator: EnergieleserFirmwareCoordinator,
        device_coordinator: EnergieleserCoordinator,
    ) -> None:
        """Initialise the update entity."""
        super().__init__(firmware_coordinator)
        self._device_type = device_coordinator.data.device_type
        self._config_entry = device_coordinator.config_entry
        self._attr_unique_id = f"{device_coordinator.device_id}_firmware"
        self._attr_title = device_model_name(self._device_type)
        self._attr_device_info = build_device_info(device_coordinator)

    @property
    @override
    def available(self) -> bool:
        """Return True if a version is published for this device type."""
        return super().available and self.latest_version is not None

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the firmware version advertised over mDNS."""
        return self._config_entry.data.get(CONF_SW_VERSION)

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest firmware version for this device type."""
        return (self.coordinator.data or {}).get(self._device_type)

    @override
    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return True if latest_version is newer than installed_version."""
        return is_newer_version(installed_version, latest_version)
