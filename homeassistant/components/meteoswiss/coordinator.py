"""DataUpdateCoordinator for MeteoSwiss integration."""

import dataclasses
import datetime
import logging

import meteoswiss_async
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POSTAL_CODE, POSTAL_CODE_ADDITIONAL_NUMBER

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(kw_only=True, frozen=True)
class MeteoSwissData:
    """Data that gets updated by the coordinator."""

    weather: meteoswiss_async.Weather


class MeteoSwissDataUpdateCoordinator(DataUpdateCoordinator[MeteoSwissData]):
    """Class to manage fetching Met data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: meteoswiss_async.MeteoSwissClient,
    ) -> None:
        """Initialize global Met data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=datetime.timedelta(minutes=5),
        )
        self._api_client = api_client
        self._postal_code: str = str(self.config_entry.data[POSTAL_CODE])
        self._additional_number: int = self.config_entry.data[
            POSTAL_CODE_ADDITIONAL_NUMBER
        ]

    async def _async_update_data(self) -> MeteoSwissData:
        """Fetch data from Meteoswiss API."""
        try:
            weather = await self._api_client.get_weather(
                postal_code=self._postal_code, additional_number=self._additional_number
            )
            return MeteoSwissData(weather=weather)
        except requests.exceptions.HTTPError as err:
            _LOGGER.error("Meteoswiss coordinator update failed", exc_info=err)
            raise UpdateFailed(f"Update failed: {err}") from err
