"""The Honeywell Lyric integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from http import HTTPStatus
import logging

from aiohttp.client_exceptions import ClientResponseError
from aiolyric import Lyric
from aiolyric.exceptions import LyricAuthenticationException, LyricException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OAuth2SessionLyric

_LOGGER = logging.getLogger(__name__)

type LyricConfigEntry = ConfigEntry[LyricDataUpdateCoordinator]


class LyricDataUpdateCoordinator(DataUpdateCoordinator[Lyric]):
    """Data update coordinator for Honeywell Lyric."""

    config_entry: LyricConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LyricConfigEntry,
        oauth_session: OAuth2SessionLyric,
        lyric: Lyric,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="lyric_coordinator",
            update_interval=timedelta(seconds=300),
        )
        self.oauth_session = oauth_session
        self.lyric = lyric

    async def _async_update_data(self) -> Lyric:
        """Fetch data from Lyric."""
        return await self._run_update(False)

    async def _run_update(self, force_refresh_token: bool) -> Lyric:
        """Fetch data from Lyric."""
        try:
            if not force_refresh_token:
                await self.oauth_session.async_ensure_token_valid()
            else:
                await self.oauth_session.force_refresh_token()
        except ClientResponseError as exception:
            if exception.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise ConfigEntryAuthFailed from exception
            raise UpdateFailed(exception) from exception

        try:
            async with asyncio.timeout(60):
                await self.lyric.get_locations()
                await asyncio.gather(
                    *(
                        self.lyric.get_thermostat_rooms(
                            location.location_id, device.device_id
                        )
                        for location in self.lyric.locations
                        for device in location.devices
                        if device.device_class == "Thermostat"
                        and device.device_id.startswith("LCC")
                    )
                )

        except LyricAuthenticationException as exception:
            # Attempt to refresh the token before failing.
            # Honeywell appear to have issues keeping tokens saved.
            _LOGGER.debug("Authentication failed. Attempting to refresh token")
            if not force_refresh_token:
                return await self._run_update(True)
            raise ConfigEntryAuthFailed from exception
        except (LyricException, ClientResponseError) as exception:
            raise UpdateFailed(exception) from exception
        return self.lyric
