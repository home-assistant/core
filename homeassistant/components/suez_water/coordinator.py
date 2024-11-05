"""Suez water update coordinator."""

import asyncio

from pysuez.async_client import SuezAsyncClient
from pysuez.exception import PySuezError
from pysuez.suez_data import AggregatedSensorData, SuezData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_COUNTER_ID, DATA_REFRESH_INTERVAL, DOMAIN


class SuezWaterCoordinator(DataUpdateCoordinator[AggregatedSensorData]):
    """Suez water coordinator."""

    _async_client: SuezAsyncClient
    _data_api: SuezData
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize suez water coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DATA_REFRESH_INTERVAL,
            always_update=True,
            config_entry=config_entry,
        )

    async def _async_setup(self) -> None:
        self._async_client = await self._get_client()
        self._data_api = SuezData(self._async_client)

    async def _async_update_data(self) -> AggregatedSensorData:
        """Fetch data from API endpoint."""
        try:
            data = await self._data_api.fetch_all_deprecated_data()
        except PySuezError as err:
            _LOGGER.exception(err)
            raise UpdateFailed(
                f"Suez coordinator error communicating with API: {err}"
            ) from err
        _LOGGER.debug("Successfully fetched suez data")
        return data


    async def _get_client(self) -> SuezAsyncClient:
        try:
            client = SuezAsyncClient(
                username=self.config_entry.data[CONF_USERNAME],
                password=self.config_entry.data[CONF_PASSWORD],
                counter_id=self.config_entry.data[CONF_COUNTER_ID],
            )
            if not await client.check_credentials():
                raise ConfigEntryError("Invalid credentials for suez water")
        except PySuezError as ex:
            raise ConfigEntryNotReady from ex
        return client
