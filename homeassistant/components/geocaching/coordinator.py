"""Provides the Geocaching DataUpdateCoordinator."""

from __future__ import annotations

from geocachingapi.exceptions import GeocachingApiError
from geocachingapi.geocachingapi import GeocachingApi
from geocachingapi.models import (
    GeocachingCoordinate,
    GeocachingSettings,
    GeocachingStatus,
    NearbyCachesSetting,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONFIG_FLOW_GEOCACHES_SECTION_ID,
    CONFIG_FLOW_TRACKABLES_SECTION_ID,
    DOMAIN,
    ENVIRONMENT,
    LOGGER,
    UPDATE_INTERVAL,
    USE_TEST_CONFIG,
)


class GeocachingDataUpdateCoordinator(DataUpdateCoordinator[GeocachingStatus]):
    """Class to manage fetching Geocaching data from single endpoint."""

    def __init__(
        self, hass: HomeAssistant, *, entry: ConfigEntry, session: OAuth2Session
    ) -> None:
        """Initialize global Geocaching data updater."""
        self.session = session
        self.entry = entry

        async def async_token_refresh() -> str:
            await session.async_ensure_token_valid()
            token = session.token["access_token"]
            LOGGER.debug(str(token))
            return str(token)

        client_session = async_get_clientsession(hass)

        settings: GeocachingSettings = GeocachingSettings()
        settings.set_nearby_caches_setting(
            NearbyCachesSetting(
                location=GeocachingCoordinate(
                    data={
                        "latitude": hass.config.latitude,
                        "longitude": hass.config.longitude,
                    }
                ),
                radiusKm=3,
            )
        )

        # TODO: Remove the hardcoded codes when development is done | pylint: disable=fixme
        trackable_codes: list[str] = (
            ["TB89YPV"]
            if USE_TEST_CONFIG
            else self.entry.data[CONFIG_FLOW_TRACKABLES_SECTION_ID]
        )
        # TODO: Validate the trackable reference codes | pylint: disable=fixme
        settings.set_trackables(trackable_codes)

        # TODO: Remove the hardcoded codes when development is done | pylint: disable=fixme
        geocache_codes: list[str] = (
            ["GC1DQPM", "GC9P6FN", "GCAKTTQ"]
            if USE_TEST_CONFIG
            else self.entry.data[CONFIG_FLOW_GEOCACHES_SECTION_ID]
        )
        # TODO: Validate the geocache reference codes | pylint: disable=fixme
        settings.set_caches(geocache_codes)

        self.geocaching = GeocachingApi(
            environment=ENVIRONMENT,
            settings=settings,
            token=session.token["access_token"],
            session=client_session,
            token_refresh_method=async_token_refresh,
        )

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> GeocachingStatus:
        try:
            return await self.geocaching.update()
        except GeocachingApiError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
