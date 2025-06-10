"""Coordinator module for Altruist integration in Home Assistant.

This module defines the AltruistDataUpdateCoordinator class, which manages
data updates for Altruist sensors using the AltruistClient.
"""

from datetime import timedelta
import logging

from altruistclient import AltruistClient, AltruistError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DEVICE_ID, CONF_IP_ADDRESS

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 15

type AltruistConfigEntry = ConfigEntry[AltruistDataUpdateCoordinator]


class AltruistDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Coordinates data updates for Altruist sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AltruistConfigEntry,
    ) -> None:
        """Initialize the data update coordinator for Altruist sensors.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            config_entry (AltruistConfigEntry): The Altruist integration config entry.
            session (ClientSession): The aiohttp client session for making HTTP requests.

        """
        device_id = config_entry.data[CONF_DEVICE_ID]
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=f"Altruist {device_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.client: AltruistClient | None = None
        self._ip_address = config_entry.data[CONF_IP_ADDRESS]

    async def _async_setup(self) -> None:
        try:
            self.client = await AltruistClient.from_ip_address(
                async_get_clientsession(self.hass), self._ip_address
            )
            await self.client.fetch_data()
        except AltruistError as e:
            raise ConfigEntryNotReady("Error in Altruist setup") from e

    async def _async_update_data(self) -> dict[str, str]:
        new_data = {}
        assert self.client
        try:
            fetched_data = await self.client.fetch_data()
        except AltruistError as ex:
            raise UpdateFailed(
                f"The Altruist {self.client.device_id} is unavailable: {ex}"
            ) from ex
        for sensordata_value in fetched_data:
            new_data[sensordata_value["value_type"]] = sensordata_value["value"]
        return new_data
