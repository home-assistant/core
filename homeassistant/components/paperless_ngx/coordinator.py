"""Paperless-ngx Status coordinator."""

from __future__ import annotations

from datetime import timedelta

from pypaperless import Paperless
from pypaperless.exceptions import (
    InitializationError,
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.models import Statistic

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type PaperlessConfigEntry = ConfigEntry[PaperlessCoordinator]

UPDATE_INTERVAL = 120


class PaperlessCoordinator(DataUpdateCoordinator[Statistic]):
    """Coordinator to manage Paperless-ngx statistic updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessConfigEntry,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="Paperless-ngx Coordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        self.api = Paperless(
            entry.data[CONF_HOST],
            entry.data[CONF_API_KEY],
            session=async_get_clientsession(self.hass),
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
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except PaperlessInactiveOrDeletedError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="user_inactive_or_deleted",
            ) from err
        except PaperlessForbiddenError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="forbidden",
            ) from err
        except InitializationError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    async def _async_update_data(self) -> Statistic:
        """Fetch data from API endpoint."""
        try:
            return await self.api.statistics()
        except PaperlessConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except PaperlessForbiddenError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="forbidden",
            ) from err
        except PaperlessInvalidTokenError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except PaperlessInactiveOrDeletedError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="user_inactive_or_deleted",
            ) from err
