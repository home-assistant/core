"""DataUpdateCoordinator for Swiss Hydrological Data."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from requests.exceptions import RequestException
from swisshydrodata import SwissHydroData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION, DOMAIN

if TYPE_CHECKING:
    from . import SwissHydroConfigEntry

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=10)


class SwissHydrologicalDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Swiss Hydrological Data."""

    config_entry: SwissHydroConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SwissHydroConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.station_id: int = entry.data[CONF_STATION]
        self._client = SwissHydroData()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Swiss Hydrological Data API."""
        try:
            data = await self.hass.async_add_executor_job(
                self._client.get_station, self.station_id
            )
        except RequestException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err

        if data is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="station_not_found",
                translation_placeholders={"station": str(self.station_id)},
            )

        return data
