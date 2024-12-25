"""Provides the Geocaching DataUpdateCoordinator."""

from __future__ import annotations

from geocachingapi.exceptions import (
    GeocachingApiError,
    GeocachingInvalidSettingsError,
    GeocachingTooManyCodesError,
)
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
    NEARBY_CACHES_COUNT_TITLE,
    NEARBY_CACHES_RADIUS_TITLE,
    UPDATE_INTERVAL,
)


class GeocachingDataUpdateCoordinator(DataUpdateCoordinator[GeocachingStatus]):
    """Class to manage fetching Geocaching data from single endpoint."""

    verified: bool = False

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
                radiusKm=self.entry.data[NEARBY_CACHES_RADIUS_TITLE],
                maxCount=self.entry.data[NEARBY_CACHES_COUNT_TITLE],
            )
        )

        settings.set_tracked_trackables(
            set(self.entry.data[CONFIG_FLOW_TRACKABLES_SECTION_ID])
        )

        settings.set_tracked_caches(
            set(self.entry.data[CONFIG_FLOW_GEOCACHES_SECTION_ID])
        )

        self.geocaching = GeocachingApi(
            environment=ENVIRONMENT,
            settings=settings,
            token=session.token["access_token"],
            session=client_session,
            token_refresh_method=async_token_refresh,
        )

        self.verified = False

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def fetch_new_status(self) -> GeocachingStatus:
        """Fetch the latest Geocaching status."""
        try:
            # If the settings have not been verified yet, do so now
            if not self.verified:
                await self.geocaching.verify_settings()
                self.verified = True
            return await self.geocaching.update()
        except GeocachingInvalidSettingsError as error:
            raise UpdateFailed(error) from error
        except GeocachingTooManyCodesError as error:
            raise UpdateFailed(error) from error
        except GeocachingApiError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error

    async def _async_update_data(self) -> GeocachingStatus:
        return await self.fetch_new_status()
