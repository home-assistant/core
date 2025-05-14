"""Coordinator for OneDrive."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging

from onedrive_personal_sdk import OneDriveClient
from onedrive_personal_sdk.const import DriveState
from onedrive_personal_sdk.exceptions import AuthenticationError, OneDriveException
from onedrive_personal_sdk.models.items import Drive

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


@dataclass
class OneDriveRuntimeData:
    """Runtime data for the OneDrive integration."""

    client: OneDriveClient
    token_function: Callable[[], Awaitable[str]]
    backup_folder_id: str
    coordinator: OneDriveUpdateCoordinator


type OneDriveConfigEntry = ConfigEntry[OneDriveRuntimeData]


class OneDriveUpdateCoordinator(DataUpdateCoordinator[Drive]):
    """Class to handle fetching data from the Graph API centrally."""

    config_entry: OneDriveConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: OneDriveConfigEntry, client: OneDriveClient
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> Drive:
        """Fetch data from API endpoint."""

        try:
            drive = await self._client.get_drive()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        except OneDriveException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err

        # create an issue if the drive is almost full
        if drive.quota and (state := drive.quota.state) in (
            DriveState.CRITICAL,
            DriveState.EXCEEDED,
        ):
            key = "drive_full" if state is DriveState.EXCEEDED else "drive_almost_full"
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                key,
                is_fixable=False,
                severity=(
                    ir.IssueSeverity.ERROR
                    if state is DriveState.EXCEEDED
                    else ir.IssueSeverity.WARNING
                ),
                translation_key=key,
                translation_placeholders={
                    "total": f"{drive.quota.total / (1024**3):.2f}",
                    "used": f"{drive.quota.used / (1024**3):.2f}",
                },
            )
        return drive
