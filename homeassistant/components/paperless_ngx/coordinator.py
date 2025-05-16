"""Paperless-ngx Status coordinator."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from aiohttp import ClientConnectionError, ClientConnectorError, ClientResponseError
from pypaperless import Paperless
from pypaperless.exceptions import BadJsonResponseError, InitializationError
from pypaperless.models import RemoteVersion, Statistic
from pypaperless.models.status import Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import now

from .const import LOGGER, REMOTE_VERSION_UPDATE_INTERVAL_HOURS

type PaperlessConfigEntry = ConfigEntry[PaperlessRuntimeData]


@dataclass(kw_only=True)
class PaperlessData:
    """Describes Paperless-ngx sensor entity."""

    remote_version: RemoteVersion | None = None
    remote_version_last_checked: datetime | None = None
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
        fetched_data = PaperlessData()

        try:
            version_current_check_time = now()
            version_last_checked_time = (
                self.data.remote_version_last_checked if self.data is not None else None
            )

            # GitHub enforces a rate limit of 60 API requests per hour if unauthorized.
            # Fetch the version only once per day to avoid hitting the limit.
            if version_last_checked_time is None or (
                version_current_check_time - version_last_checked_time
            ) >= timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS):
                fetched_data.remote_version = await self.get_paperless_remote_version(
                    self.api
                )
                fetched_data.remote_version_last_checked = version_current_check_time
            else:
                fetched_data.remote_version = (
                    self.data.remote_version if self.data else None
                )
                fetched_data.remote_version_last_checked = version_last_checked_time

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
        """Get the remote version of Paperless-ngx."""
        try:
            version = await api.remote_version()
            if version.version == "0.0.0":
                LOGGER.warning(
                    "Could not fetch remote version from Paperless-ngx API",
                    exc_info=True,
                )
                return None
            return version  # noqa: TRY300
        except Exception as err:  # noqa: BLE001
            LOGGER.warning(
                "Could not fetch remote version from Paperless-ngx API: %s",
                err,
                exc_info=True,
            )
            return None

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
