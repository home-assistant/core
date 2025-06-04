"""Coordinator module for Altruist integration in Home Assistant.

This module defines the AltruistDataUpdateCoordinator class, which manages
data updates for Altruist sensors using the AltruistClient.
"""

from datetime import timedelta
import logging

from altruistclient import AltruistClient, AltruistError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AltruistDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinates data updates for Altruist sensors."""

    def __init__(self, hass: HomeAssistant, client: AltruistClient) -> None:
        """Initialize the data update coordinator for Altruist sensors.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            client (AltruistClient): The client to interact with Altruist devices.

        """
        super().__init__(
            hass,
            _LOGGER,
            name="Altruist",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self._client = client

    async def _async_update_data(self) -> dict:
        try:
            fetched_data = await self._client.fetch_data()
            new_data = {}
            for sensordata_value in fetched_data:
                new_data[sensordata_value["value_type"]] = sensordata_value["value"]
        except AltruistError as ex:
            raise UpdateFailed(
                f"The Altruist Sensor {self._client.device_id} is unavailable: {ex}"
            ) from ex
        else:
            return new_data
