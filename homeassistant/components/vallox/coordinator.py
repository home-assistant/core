"""Coordinator for Vallox ventilation units."""

from __future__ import annotations

import logging

from vallox_websocket_api import MetricData, Vallox, ValloxApiException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import STATE_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class ValloxDataUpdateCoordinator(DataUpdateCoordinator[MetricData]):
    """The DataUpdateCoordinator for Vallox."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        client: Vallox,
    ) -> None:
        """Initialize Vallox data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{name} DataUpdateCoordinator",
            update_interval=STATE_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> MetricData:
        """Fetch state update."""
        _LOGGER.debug("Updating Vallox state cache")

        try:
            return await self.client.fetch_metric_data()
        except ValloxApiException as err:
            raise UpdateFailed("Error during state cache update") from err
