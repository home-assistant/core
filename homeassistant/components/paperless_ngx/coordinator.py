"""Paperless-ngx Status coordinator."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from pypaperless import Paperless
from pypaperless.exceptions import (
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.models import RemoteVersion, Statistic
from pypaperless.models.status import Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import now

from .const import DOMAIN, LOGGER, REMOTE_VERSION_UPDATE_INTERVAL_HOURS

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
        self.github_ratelimit_reached_logged: bool = False
        self.status_forbidden_logged: bool = False
        self.statistics_forbidden_logged: bool = False

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        fetched_data = PaperlessData()

        try:
            (
                fetched_data.remote_version,
                fetched_data.remote_version_last_checked,
            ) = await self._get_paperless_remote_version(self.api)
            fetched_data.status = await self._get_paperless_status(self.api)
            fetched_data.statistics = await self._get_paperless_statistics(self.api)

        except PaperlessInvalidTokenError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except PaperlessInactiveOrDeletedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="user_inactive_or_deleted",
            ) from err

        return fetched_data

    async def _get_paperless_remote_version(
        self, api: Paperless
    ) -> tuple[RemoteVersion | None, datetime | None]:
        """Fetch the latest version of Paperless-ngx if required."""

        if not self._should_fetch_remote_version():
            return (
                self.data.remote_version if self.data else None,
                self.data.remote_version_last_checked if self.data else None,
            )

        version = await api.remote_version()
        if version.version == "0.0.0":
            if not self.github_ratelimit_reached_logged:
                LOGGER.warning(
                    "Received version '0.0.0' from Paperless-ngx API - this likely indicates "
                    "the GitHub rate limit of 60 requests per hour is reached",
                    exc_info=True,
                )
                self.github_ratelimit_reached_logged = True
            return None, now()

        self.github_ratelimit_reached_logged = False
        return version, now()

    def _should_fetch_remote_version(self) -> bool:
        """Determine whether the remote version of Paperless-ngx should be fetched.

        GitHub enforces a rate limit of 60 API requests per hour if unauthorized.
        To avoid hitting the limit, the remote version is fetched only once per day.
        """

        current_time = now()
        last_checked = self.data.remote_version_last_checked if self.data else None

        if last_checked is None:
            return True
        return (current_time - last_checked) >= timedelta(
            hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS
        )

    async def _get_paperless_status(self, api: Paperless) -> Status | None:
        """Get the status of Paperless-ngx."""
        try:
            status = await api.status()
        except PaperlessForbiddenError as err:
            if not self.status_forbidden_logged:
                LOGGER.warning(
                    "Could not fetch status from Paperless-ngx due missing permissions: %s",
                    err,
                    exc_info=True,
                )
                self.status_forbidden_logged = True
            return None
        else:
            self.statistics_forbidden_logged = False
            return status

    async def _get_paperless_statistics(self, api: Paperless) -> Statistic | None:
        """Get the status of Paperless-ngx."""
        try:
            statistics = await api.statistics()
        except PaperlessForbiddenError as err:
            if not self.statistics_forbidden_logged:
                LOGGER.warning(
                    "Could not fetch statistics from Paperless-ngx due missing permissions: %s",
                    err,
                    exc_info=True,
                )
                self.statistics_forbidden_logged = True
            return None
        else:
            self.statistics_forbidden_logged = False
            return statistics


@dataclass(kw_only=True)
class PaperlessRuntimeData:
    """Describes Paperless-ngx runtime data."""

    client: Paperless
    coordinator: PaperlessCoordinator
