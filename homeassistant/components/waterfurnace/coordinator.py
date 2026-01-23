"""Data update coordinator for WaterFurnace."""

import logging

from waterfurnace.waterfurnace import WaterFurnace, WFException, WFReading

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class WaterFurnaceCoordinator(DataUpdateCoordinator[WFReading]):
    """WaterFurnace data update coordinator.

    Polls the WaterFurnace API regularly to keep the websocket connection alive.
    The server closes the connection if no data is requested for 30 seconds,
    so frequent polling is necessary.
    """

    def __init__(
        self, hass: HomeAssistant, client: WaterFurnace, config_entry=None
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="WaterFurnace",
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.unit = client.gwid

    async def _async_update_data(self):
        """Fetch data from WaterFurnace API with built-in retry logic."""
        try:
            return await self.hass.async_add_executor_job(self.client.read_with_retry)
        except WFException as err:
            raise UpdateFailed(str(err)) from err
