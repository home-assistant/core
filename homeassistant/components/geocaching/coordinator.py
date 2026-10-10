"""Provides the Geocaching DataUpdateCoordinator."""

from dataclasses import dataclass
from typing import override

from geocachingapi.exceptions import GeocachingApiError, GeocachingInvalidSettingsError
from geocachingapi.geocachingapi import GeocachingApi
from geocachingapi.models import (
    GeocachingCache,
    GeocachingSettings,
    GeocachingTrackable,
    GeocachingUser,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_TRACKABLE_CODES,
    DOMAIN,
    ENVIRONMENT,
    LOGGER,
    SUBENTRY_TYPE_TRACKED_CACHE,
    UPDATE_INTERVAL,
)

type GeocachingConfigEntry = ConfigEntry[GeocachingDataUpdateCoordinator]


@dataclass(frozen=True)
class GeocachingCoordinatorData:
    """Data returned by the Geocaching coordinator."""

    user: GeocachingUser
    trackables: dict[str, GeocachingTrackable]
    nearby_caches: list[GeocachingCache]
    tracked_caches: dict[str, GeocachingCache]


class GeocachingDataUpdateCoordinator(DataUpdateCoordinator[GeocachingCoordinatorData]):
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
        settings.set_tracked_caches(
            {
                subentry.data[CONF_CODE]
                for subentry in entry.get_subentries_of_type(
                    SUBENTRY_TYPE_TRACKED_CACHE
                )
            }
        )
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
    async def _async_update_data(self) -> GeocachingCoordinatorData:
        """Fetch the latest Geocaching status."""
        try:
            status = await self.geocaching.update()
        except GeocachingInvalidSettingsError as error:
            raise UpdateFailed(f"Invalid integration configuration: {error}") from error
        except GeocachingApiError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error

        return GeocachingCoordinatorData(
            user=status.user,
            trackables={
                trackable.reference_code.strip().upper(): trackable
                for trackable in status.trackables.values()
                if isinstance(trackable.reference_code, str)
            },
            nearby_caches=status.nearby_caches,
            tracked_caches={
                cache.reference_code.strip().upper(): cache
                for cache in status.tracked_caches
                if cache.reference_code is not None
            },
        )
