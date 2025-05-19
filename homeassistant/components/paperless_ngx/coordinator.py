"""Paperless-ngx Status coordinator."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from pypaperless import Paperless
from pypaperless.exceptions import (
    InitializationError,
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.models import RemoteVersion, Statistic
from pypaperless.models.status import Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import now

from .const import DOMAIN, LOGGER, REMOTE_VERSION_UPDATE_INTERVAL_HOURS


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
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Paperless-ngx Coordinator",
            update_interval=timedelta(seconds=120),
            always_update=True,
        )
        self.github_ratelimit_reached_logged: bool = False
        self.status_forbidden_logged: bool = False
        self.statistics_forbidden_logged: bool = False

        aiohttp_session = async_get_clientsession(self.hass)
        self.api = Paperless(
            entry.data[CONF_HOST],
            entry.data[CONF_API_KEY],
            session=aiohttp_session,
        )

    async def _async_setup(self) -> None:
        try:
            await self.api.initialize()
            await self.api.statistics()  # test permissions on api
        except PaperlessConnectionError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except PaperlessInvalidTokenError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except PaperlessInactiveOrDeletedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="user_inactive_or_deleted",
            ) from err
        except PaperlessForbiddenError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="forbidden",
            ) from err
        except InitializationError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    async def _async_update_data(self) -> PaperlessData:
        """Fetch data from API endpoint."""
        data = PaperlessData()

        try:
            (
                data.remote_version,
                data.remote_version_last_checked,
            ) = await self._get_paperless_remote_version()
            data.status = await self._get_paperless_status()
            data.statistics = await self._get_paperless_statistics()

        except PaperlessInvalidTokenError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except PaperlessInactiveOrDeletedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="user_inactive_or_deleted",
            ) from err

        return data

    async def _get_paperless_remote_version(
        self,
    ) -> tuple[RemoteVersion | None, datetime | None]:
        """Fetch the latest version of Paperless-ngx if required."""

        if not self._should_fetch_remote_version():
            return (
                self.data.remote_version if self.data else None,
                self.data.remote_version_last_checked if self.data else None,
            )

        version = await self.api.remote_version()
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

    async def _get_paperless_status(self) -> Status | None:
        """Get the status of Paperless-ngx."""
        try:
            status = await self.api.status()
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

    async def _get_paperless_statistics(self) -> Statistic | None:
        """Get the status of Paperless-ngx."""
        try:
            statistics = await self.api.statistics()
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
