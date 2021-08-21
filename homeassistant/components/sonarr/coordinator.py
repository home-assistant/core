"""Coordinator for Sonarr."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from sonarr import Sonarr, SonarrAccessRestricted, SonarrError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


class SonarrDataUpdateCoordinator(DataUpdateCoordinator[Device]):
    """Class to manage fetching Sonarr data."""

    last_full_update: datetime | None
    sonarr: Sonarr

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        api_key: str,
        base_path: str,
        tls: bool,
        verify_ssl: bool,
    ) -> None:
        """Initialize global Sonarr data updater."""
        self.sonarr = Sonarr(
            host=host,
            port=port,
            api_key=api_key,
            base_path=base_path,
            session=async_get_clientsession(hass),
            tls=tls,
            verify_ssl=verify_ssl,
        )

        self.full_update_interval = timedelta(minutes=15)
        self.last_full_update = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> Device:
        """Fetch data from Sonarr."""
        full_update = self.last_full_update is None or utcnow() >= (
            self.last_full_update + self.full_update_interval
        )

        try:
            data = await self.sonarr.update()

            if full_update:
                self.last_full_update = utcnow()

            return data
        except SonarrError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
