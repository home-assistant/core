"""Coordinator for EPS integration."""
import asyncio
from datetime import timedelta
import logging

from pyepsalarm import EPS

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, EPS_TO_HASS

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class EPSDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching EPS data."""

    def __init__(self, hass: HomeAssistant, eps_api: EPS, site: str) -> None:
        """Initialize global EPS data updater."""
        self.eps_api = eps_api
        self.state: str | None = None
        self.site = site
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def _update_data(self) -> None:
        """Fetch data from EPS via sync functions."""
        status = self.eps_api.get_status()
        _LOGGER.debug("EPS status: %s", status)
        self.state = EPS_TO_HASS.get(status, status)

    async def _async_update_data(self) -> None:
        """Fetch data from EPS."""
        try:
            async with asyncio.timeout(10):
                await self.hass.async_add_executor_job(self._update_data)
        except ConnectionError as error:
            raise UpdateFailed(error) from error
