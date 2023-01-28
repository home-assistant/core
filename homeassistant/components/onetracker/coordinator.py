"""Provides the OneTracker DataUpdateCoordinator."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

from async_timeout import timeout

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OneTrackerAPI, OneTrackerAPIException
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OneTrackerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching OneTracker data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config: Mapping[str, Any],
        options: Mapping[str, Any] | None = None,
    ) -> None:
        """Initialize global OneTracker data updater."""

        update_interval = timedelta(seconds=config[CONF_SCAN_INTERVAL])

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

        self.onetracker = OneTrackerAPI(
            config[CONF_EMAIL],
            config[CONF_PASSWORD],
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from OneTracker."""

        def _update_data() -> dict:
            """Fetch data from OneTracker via sync functions."""
            return self.onetracker.get_parcels()

        try:
            async with timeout(4):
                return await self.hass.async_add_executor_job(_update_data)
        except OneTrackerAPIException as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
