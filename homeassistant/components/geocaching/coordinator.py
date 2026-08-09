"""Provides the Geocaching DataUpdateCoordinator."""

from typing import override

from geocachingapi.exceptions import GeocachingApiError, GeocachingInvalidSettingsError
from geocachingapi.geocachingapi import GeocachingApi
from geocachingapi.models import GeocachingSettings, GeocachingStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CACHE_CODES,
    CONF_TRACKABLE_CODES,
    DOMAIN,
    ENVIRONMENT,
    LOGGER,
    UPDATE_INTERVAL,
)

type GeocachingConfigEntry = ConfigEntry[GeocachingDataUpdateCoordinator]


class GeocachingDataUpdateCoordinator(DataUpdateCoordinator[GeocachingStatus]):
    """Class to manage fetching Geocaching data from single endpoint."""

    config_entry: GeocachingConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: GeocachingConfigEntry,
        session: OAuth2Session,
    ) -> None:
        """Initialize global Geocaching data updater."""
        self.session = session

        async def async_token_refresh() -> str:
            await session.async_ensure_token_valid()
            token = session.token["access_token"]
            return str(token)

        client_session = async_get_clientsession(hass)
        settings = GeocachingSettings()
        settings.set_tracked_caches(set(entry.options.get(CONF_CACHE_CODES, [])))
        settings.set_tracked_trackables(
            set(entry.options.get(CONF_TRACKABLE_CODES, []))
        )
        self.geocaching = GeocachingApi(
            environment=ENVIRONMENT,
            token=session.token["access_token"],
            settings=settings,
            session=client_session,
            token_refresh_method=async_token_refresh,
        )

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> GeocachingStatus:
        """Fetch the latest Geocaching status."""
        try:
            return await self.geocaching.update()
        except GeocachingInvalidSettingsError as error:
            raise UpdateFailed(f"Invalid integration configuration: {error}") from error
        except GeocachingApiError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
