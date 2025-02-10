"""Coordinator for OneDrive."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging

from onedrive_personal_sdk import OneDriveClient
from onedrive_personal_sdk.exceptions import AuthenticationError, OneDriveException
from onedrive_personal_sdk.models.items import Drive

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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
    """Class to handle fetching data from the tedee API centrally."""

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
        return drive
