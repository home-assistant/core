"""The IntelliFire integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import logging.handlers

from async_timeout import timeout
from intellifire4py import IntellifireAsync

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN


class IntellifireDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage the polling of the fireplace API."""

    def __init__(self, hass, api: IntellifireAsync, serial: str):
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
            update_method=self._async_update_data,
        )
        self._api = api
        self.serial = serial
        self._LOGGER = _LOGGER

    async def _async_update_data(self):
        _LOGGER.debug("Calling update loop on IntelliFire")
        async with timeout(100):
            try:
                await self._api.poll(logging_level=logging.DEBUG)
            except Exception as e:
                raise UpdateFailed from e
        return self._api.data

    @property
    def api(self):
        """Return the API pointer."""
        return self._api
