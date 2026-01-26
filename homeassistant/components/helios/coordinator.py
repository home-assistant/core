"""Coordinator for Helios ventilation units."""

from __future__ import annotations

import logging

from helios_websocket_api import MetricData, Helios, HeliosApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import STATE_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HeliosDataUpdateCoordinator(DataUpdateCoordinator[MetricData]):
    """The DataUpdateCoordinator for Helios."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: Helios,
    ) -> None:
        """Initialize Helios data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{config_entry.data[CONF_NAME]} DataUpdateCoordinator",
            update_interval=STATE_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> MetricData:
        """Fetch state update."""
        _LOGGER.debug("Updating Helios state cache")

        try:
            return await self.client.fetch_metric_data()
        except HeliosApiException as err:
            raise UpdateFailed("Error during state cache update") from err
