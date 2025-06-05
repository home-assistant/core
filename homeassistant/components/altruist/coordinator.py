"""Coordinator module for Altruist integration in Home Assistant.

This module defines the AltruistDataUpdateCoordinator class, which manages
data updates for Altruist sensors using the AltruistClient.
"""

from datetime import timedelta
import logging

from aiohttp import ClientSession
from altruistclient import AltruistClient, AltruistError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
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
        session: ClientSession,
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
        self._session = session

    async def _async_setup(self) -> None:
        try:
            self.client = await AltruistClient.from_ip_address(
                self._session, self._ip_address
            )
            await self.client.fetch_data()
        except Exception as e:
            _LOGGER.error("Error in Altruist setup: %s", e)
            raise ConfigEntryNotReady from e

    async def _async_update_data(self) -> dict[str, str]:
        new_data = {}
        if self.client is not None:
            try:
                fetched_data = await self.client.fetch_data()
            except AltruistError as ex:
                raise UpdateFailed(
                    f"The Altruist Sensor {self.client.device_id} is unavailable: {ex}"
                ) from ex
            for sensordata_value in fetched_data:
                new_data[sensordata_value["value_type"]] = sensordata_value["value"]
        return new_data
