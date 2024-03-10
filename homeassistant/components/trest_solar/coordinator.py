from __future__ import annotations  # noqa: D100

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import REFRESH_INTERVAL
from .domain.solar_history import SolarHistory
from .services.trest_solar_service import CloudSolarTrestService

_LOGGER = logging.getLogger(__name__)


class TrestDataCoordinator(DataUpdateCoordinator[SolarHistory]):
    """Trest coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        trest_solar_service: CloudSolarTrestService,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger,
            name="Trest Solar Controller",
            update_interval=timedelta(seconds=REFRESH_INTERVAL),
        )
        self.trest_solar_service = trest_solar_service

    async def _async_update_data(self) -> SolarHistory:
        """Fetch data from Trest Cloud."""

        _LOGGER.info("Requesting Solar History data from Cloud Trest")
        response = await self.trest_solar_service.get_latest_solar_history_async()

        solar_history = SolarHistory(response)

        return solar_history

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup.

        Will automatically raise ConfigEntryNotReady if the refresh
        fails. Additionally logging is handled by config entry setup
        to ensure that multiple retries do not cause log spam.
        """
        await self._async_refresh(
            log_failures=False, raise_on_auth_failed=True, raise_on_entry_error=True
        )
        if self.last_update_success:
            return
        ex = ConfigEntryNotReady()
        ex.__cause__ = self.last_exception
        raise ex

    async def async_refresh(self) -> None:
        """Refresh data and log errors."""
        await self._async_refresh(log_failures=True)
