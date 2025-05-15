"""Paperless-ngx Status coordinator."""

from dataclasses import dataclass
from datetime import timedelta

from aiohttp import ClientConnectionError, ClientConnectorError, ClientResponseError
from pypaperless import Paperless
from pypaperless.exceptions import BadJsonResponseError, InitializationError
from pypaperless.models import RemoteVersion, Statistic
from pypaperless.models.status import Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER

type PaperlessConfigEntry = ConfigEntry[PaperlessRuntimeData]


@dataclass(kw_only=True)
class PaperlessData:
    """Describes Paperless-ngx sensor entity."""

    remote_version: RemoteVersion | None = None
    status: Status | None = None
    statistics: Statistic | None = None


class PaperlessCoordinator(DataUpdateCoordinator[PaperlessData]):
    """Coordinator to manage Paperless-ngx status updates."""

    def __init__(
        self, hass: HomeAssistant, entry: PaperlessConfigEntry, api: Paperless
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Paperless-ngx Coordinator",
            config_entry=entry,
            update_interval=timedelta(seconds=entry.data[CONF_SCAN_INTERVAL]),
            always_update=True,
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            fetched_data = PaperlessData()
            fetched_data.remote_version = await self.get_paperless_remote_version(
                self.api
            )
            fetched_data.status = await self.get_paperless_status(self.api)
            fetched_data.statistics = await self.get_paperless_statistics(self.api)

        except (
            InitializationError,
            ClientConnectorError,
            ClientConnectionError,
        ) as err:
            LOGGER.error(
                "Failed to connect to Paperless-ngx API: %s",
                err,
                exc_info=True,
            )
        except ClientResponseError as err:
            if err.status == 401:
                LOGGER.error(
                    "Invalid authentication credentials for Paperless-ngx API: %s",
                    err,
                    exc_info=True,
                )
            elif err.status == 403:
                LOGGER.error(
                    "Access forbidden to Paperless-ngx API: %s",
                    err,
                    exc_info=True,
                )
            else:
                LOGGER.error("Unexpected error: %s", err)
        except Exception as err:  # noqa: BLE001
            LOGGER.error(
                "An error occurred while updating the Paperless-ngx sensor: %s",
                err,
                exc_info=True,
            )

        return fetched_data

    async def get_paperless_remote_version(
        self, api: Paperless
    ) -> RemoteVersion | None:
        """Get the status of Paperless-ngx."""
        try:
            return await api.remote_version()
        except (ClientResponseError, BadJsonResponseError) as err:
            if (
                isinstance(err, ClientResponseError) and err.status == 403
            ) or isinstance(err, BadJsonResponseError):
                return None
            raise

    async def get_paperless_status(self, api: Paperless) -> Status | None:
        """Get the status of Paperless-ngx."""
        try:
            return await api.status()
        except (ClientResponseError, BadJsonResponseError) as err:
            if (
                isinstance(err, ClientResponseError) and err.status == 403
            ) or isinstance(err, BadJsonResponseError):
                return None
            raise

    async def get_paperless_statistics(self, api: Paperless) -> Statistic | None:
        """Get the status of Paperless-ngx."""
        try:
            return await api.statistics()
        except (ClientResponseError, BadJsonResponseError) as err:
            if (
                isinstance(err, ClientResponseError) and err.status == 403
            ) or isinstance(err, BadJsonResponseError):
                return None
            raise


@dataclass(kw_only=True)
class PaperlessRuntimeData:
    """Describes Paperless-ngx sensor entity."""

    client: Paperless
    coordinator: PaperlessCoordinator
