"""Support for QNAP NAS firmware update entity."""

from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QnapConfigEntry, QnapCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QnapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up QNAP update entities."""
    coordinator = config_entry.runtime_data
    uid = config_entry.unique_id
    assert uid is not None
    async_add_entities([QNAPFirmwareUpdateEntity(coordinator, uid)])


class QNAPFirmwareUpdateEntity(CoordinatorEntity[QnapCoordinator], UpdateEntity):
    """Update entity for QNAP NAS firmware."""

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: QnapCoordinator, unique_id: str) -> None:
        """Initialize the QNAP firmware update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}_firmware_update"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            serial_number=unique_id,
            name=coordinator.data["system_stats"]["system"]["name"],
            model=coordinator.data["system_stats"]["system"]["model"],
            sw_version=coordinator.data["system_stats"]["firmware"]["version"],
            manufacturer="QNAP",
        )

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version."""
        return self.coordinator.data["system_stats"]["firmware"]["version"]

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version.

        Returns None when no update information is available or the
        coordinator reports an error state (treated as up-to-date by Home
        Assistant). Returns the version string when a firmware update is
        available.
        """
        available: str | None = self.coordinator.data.get("firmware_update")
        if not available or available == "error":
            return None
        return available
