"""Coordinator for the Immich integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from awesomeversion import AwesomeVersion
from immichpy import AsyncClient
from immichpy.client.generated.exceptions import UnauthorizedException
from immichpy.client.generated.models.server_about_response_dto import (
    ServerAboutResponseDto,
)
from immichpy.client.generated.models.server_stats_response_dto import (
    ServerStatsResponseDto,
)
from immichpy.client.generated.models.server_storage_response_dto import (
    ServerStorageResponseDto,
)
from immichpy.client.generated.models.version_check_state_response_dto import (
    VersionCheckStateResponseDto,
)
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONNECT_ERRORS, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class ImmichData:
    """Data class for storing data from the API."""

    server_about: ServerAboutResponseDto
    server_storage: ServerStorageResponseDto
    server_usage: ServerStatsResponseDto | None
    server_version_check: VersionCheckStateResponseDto | None


type ImmichConfigEntry = ConfigEntry[ImmichDataUpdateCoordinator]


class ImmichDataUpdateCoordinator(DataUpdateCoordinator[ImmichData]):
    """Class to manage fetching Immich data from the API."""

    config_entry: ImmichConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ImmichConfigEntry) -> None:
        """Initialize the data update coordinator."""
        base_url = str(
            URL.build(
                scheme="https" if config_entry.data[CONF_SSL] else "http",
                host=config_entry.data[CONF_HOST],
                port=config_entry.data[CONF_PORT],
            )
        )
        self.api = AsyncClient(
            api_key=config_entry.data[CONF_API_KEY],
            base_url=f"{base_url}/api",
            http_client=async_get_clientsession(hass, config_entry.data[CONF_VERIFY_SSL]),
        )
        self.is_admin = False
        self.configuration_url = base_url
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    async def _async_setup(self) -> None:
        """Handle setup of the coordinator."""
        try:
            user_info = await self.api.users.get_my_user()
        except UnauthorizedException as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except CONNECT_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        self.is_admin = user_info.is_admin

    async def _async_update_data(self) -> ImmichData:
        """Update data via internal method."""
        try:
            server_about = await self.api.server.get_about_info()
            server_storage = await self.api.server.get_storage()
            server_usage = (
                await self.api.server.get_server_statistics()
                if self.is_admin
                else None
            )
            server_version_check = (
                await self.api.server.get_version_check()
                if AwesomeVersion(server_about.version) >= AwesomeVersion("v1.134.0")
                else None
            )
        except UnauthorizedException as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except CONNECT_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": repr(err)},
            ) from err

        return ImmichData(
            server_about, server_storage, server_usage, server_version_check
        )
