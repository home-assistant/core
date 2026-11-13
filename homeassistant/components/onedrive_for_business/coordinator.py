"""Coordinator for OneDrive for Business."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from time import time
from typing import override

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
    coordinator: OneDriveForBusinessUpdateCoordinator


type OneDriveConfigEntry = ConfigEntry[OneDriveRuntimeData]


class OneDriveForBusinessUpdateCoordinator(DataUpdateCoordinator[Drive]):
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

    @override
    async def _async_update_data(self) -> Drive:
        """Fetch data from API endpoint."""
        expires_at = self.config_entry.data["token"]["expires_at"]
        _LOGGER.debug(
            "Token expiry: %s (in %s seconds)",
            expires_at,
            expires_at - time(),
        )

        try:
            drive = await self._client.get_drive()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        except OneDriveException as err:
            _LOGGER.debug("Failed to fetch drive data: %s", err, exc_info=True)
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err

        if not drive.quota:
            return drive

        entry_id = self.config_entry.entry_id
        key: str | None = None
        # create an issue if the drive is almost full
        if (state := drive.quota.state) in (DriveState.CRITICAL, DriveState.EXCEEDED):
            key = "drive_full" if state is DriveState.EXCEEDED else "drive_almost_full"
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{key}_{entry_id}",
                is_fixable=False,
                severity=(
                    ir.IssueSeverity.ERROR
                    if state is DriveState.EXCEEDED
                    else ir.IssueSeverity.WARNING
                ),
                translation_key=key,
                translation_placeholders={
                    "name": self.config_entry.title,
                    "total": f"{drive.quota.total / (1024**3):.2f}",
                    "used": f"{drive.quota.used / (1024**3):.2f}",
                },
                config_entry_id=entry_id,
            )
        for stale_key in ("drive_full", "drive_almost_full"):
            if stale_key != key:
                ir.async_delete_issue(self.hass, DOMAIN, f"{stale_key}_{entry_id}")
        return drive
