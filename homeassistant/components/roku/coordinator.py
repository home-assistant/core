"""Coordinator for Roku."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from rokuecp import Roku, RokuError
from rokuecp.models import Device

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import DOMAIN

REQUEST_REFRESH_DELAY = 0.35

SCAN_INTERVAL = timedelta(seconds=10)
_LOGGER = logging.getLogger(__name__)


class RokuDataUpdateCoordinator(DataUpdateCoordinator[Device]):
    """Class to manage fetching Roku data."""

    last_full_update: datetime | None
    roku: Roku

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
    ) -> None:
        """Initialize global Roku data updater."""
        self.roku = Roku(host=host, session=async_get_clientsession(hass))

        self.full_update_interval = timedelta(minutes=15)
        self.last_full_update = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> Device:
        """Fetch data from Roku."""
        full_update = self.last_full_update is None or utcnow() >= (
            self.last_full_update + self.full_update_interval
        )

        try:
            data = await self.roku.update(full_update=full_update)

            if full_update:
                self.last_full_update = utcnow()

            return data
        except RokuError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
