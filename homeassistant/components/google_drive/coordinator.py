"""DataUpdateCoordinator for Google Drive."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from google_drive_api.exceptions import GoogleDriveApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DriveClient, StorageQuotaData
from .const import DOMAIN, SCAN_INTERVAL

type GoogleDriveConfigEntry = ConfigEntry[GoogleDriveDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


@dataclass
class SensorData:
    """Class to represent sensor data."""

    storage_quota: StorageQuotaData
    all_backups_size: int


class GoogleDriveDataUpdateCoordinator(DataUpdateCoordinator[SensorData]):
    """Class to manage fetching Google Drive data from single endpoint."""

    client: DriveClient
    config_entry: GoogleDriveConfigEntry
    email_address: str
    backup_folder_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: DriveClient,
        backup_folder_id: str,
        entry: GoogleDriveConfigEntry,
    ) -> None:
        """Initialize Google Drive data updater."""
        self.client = client
        self.backup_folder_id = backup_folder_id

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_setup(self) -> None:
        """Do initialization logic."""
        self.email_address = await self.client.async_get_email_address()

    async def _async_update_data(self) -> SensorData:
        """Fetch data from Google Drive."""
        try:
            storage_quota = await self.client.async_get_storage_quota()
            all_backups_size = await self.client.async_get_size_of_all_backups()
            return SensorData(
                storage_quota=storage_quota,
                all_backups_size=all_backups_size,
            )
        except GoogleDriveApiError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response_google_drive_error",
                translation_placeholders={"error": str(error)},
            ) from error
