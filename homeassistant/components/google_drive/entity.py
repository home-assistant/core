"""Define the Google Drive entity."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DRIVE_FOLDER_URL_PREFIX
from .coordinator import GoogleDriveDataUpdateCoordinator


class GoogleDriveEntity(CoordinatorEntity[GoogleDriveDataUpdateCoordinator]):
    """Defines a base Google Drive entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Google Drive device."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self.coordinator.config_entry.unique_id))},
            name=self.coordinator.email_address,
            manufacturer="Google",
            model="Google Drive",
            configuration_url=f"{DRIVE_FOLDER_URL_PREFIX}{self.coordinator.backup_folder_id}",
            entry_type=DeviceEntryType.SERVICE,
        )
