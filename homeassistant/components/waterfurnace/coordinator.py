"""Data update coordinator for WaterFurnace."""

import logging
from typing import TYPE_CHECKING

from waterfurnace.waterfurnace import WaterFurnace, WFException, WFGateway, WFReading

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import WaterFurnaceConfigEntry

_LOGGER = logging.getLogger(__name__)


class WaterFurnaceCoordinator(DataUpdateCoordinator[WFReading]):
    """WaterFurnace data update coordinator.

    Polls the WaterFurnace API regularly to keep the websocket connection alive.
    The server closes the connection if no data is requested for 30 seconds,
    so frequent polling is necessary.
    """

    device_metadata: WFGateway | None

    def __init__(
        self,
        hass: HomeAssistant,
        client: WaterFurnace,
        config_entry: WaterFurnaceConfigEntry,
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
        self.unit = str(client.gwid)
        self.device_metadata = None
        if client.devices is not None:
            self.device_metadata = next(
                (device for device in client.devices if device.gwid == self.unit), None
            )

    async def _async_update_data(self):
        """Fetch data from WaterFurnace API with built-in retry logic."""
        try:
            return await self.hass.async_add_executor_job(self.client.read_with_retry)
        except WFException as err:
            raise UpdateFailed(str(err)) from err
