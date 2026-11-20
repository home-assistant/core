"""Coordinate a single poll for all entities belonging to a location."""

import logging
from typing import override

from xiaomi_weather import WeatherData, XiaomiWeatherClient, XiaomiWeatherError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CITY_ID, DOMAIN, UPDATE_INTERVAL

type XiaomiWeatherConfigEntry = ConfigEntry[XiaomiWeatherCoordinator]


def validate_current_temperature(data: WeatherData) -> None:
    """Require current temperature in the entity's supported native unit."""
    if data.current.temperature.unit != "℃":
        raise XiaomiWeatherError("Unsupported current temperature unit")


class XiaomiWeatherCoordinator(DataUpdateCoordinator[WeatherData]):
    """Manage fetching, availability and automatic recovery."""

    config_entry: XiaomiWeatherConfigEntry

    def __init__(self, hass: HomeAssistant, entry: XiaomiWeatherConfigEntry) -> None:
        """Initialize the shared client."""
        super().__init__(
            hass,
            logging.getLogger(__name__),
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.client = XiaomiWeatherClient(async_get_clientsession(hass))

    @override
    async def _async_update_data(self) -> WeatherData:
        """Translate client failures to recoverable coordinator errors."""
        try:
            data = await self.client.get_weather(
                self.config_entry.data[CONF_CITY_ID],
                self.config_entry.data[CONF_LATITUDE],
                self.config_entry.data[CONF_LONGITUDE],
            )
            validate_current_temperature(data)
        except XiaomiWeatherError as err:
            raise UpdateFailed("Unable to update Xiaomi weather") from err
        return data
