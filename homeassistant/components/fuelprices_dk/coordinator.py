"""Coordinator for the Fuelprices.dk integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from aiohttp import ClientConnectionError, ClientResponseError
from pybraendstofpriser import Braendstofpriser

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailedUnreachable,
)

from .const import CONF_STATION, DOMAIN, SUBENTRY_TYPE_STATION

if TYPE_CHECKING:
    from . import FuelpricesDkConfigEntry

SCAN_INTERVAL = timedelta(hours=1)

_LOGGER = logging.getLogger(__name__)


@dataclass
class FuelPricesDKStation:
    """Station data returned by the API."""

    name: str
    prices: dict[str, str]


class FuelPricesDKCoordinator(DataUpdateCoordinator[dict[int, FuelPricesDKStation]]):
    """Data update coordinator for the Fuelprices.dk integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FuelpricesDkConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

        self._api = Braendstofpriser(config_entry.data[CONF_API_KEY])
        self._station_ids = [
            subentry.data[CONF_STATION]["id"]
            for subentry in config_entry.get_subentries_of_type(SUBENTRY_TYPE_STATION)
        ]

    @override
    async def _async_update_data(self) -> dict[int, FuelPricesDKStation]:
        """Handle data update request from the coordinator."""
        if not self._station_ids:
            return {}

        try:
            data = await self._api.get_prices_bulk(self._station_ids)
        except ClientResponseError as exc:
            if exc.status == 401:
                raise ConfigEntryAuthFailed(exc) from exc
            if exc.status == 429 or 500 <= exc.status < 600:
                raise UpdateFailedUnreachable(f"HTTP {exc.status}") from exc
            raise
        except TimeoutError as exc:
            raise UpdateFailedUnreachable("Request timed out") from exc
        except ClientConnectionError as exc:
            raise UpdateFailedUnreachable(str(exc)) from exc

        return {
            item["station"]["id"]: FuelPricesDKStation(
                name=item["station"]["name"], prices=item["prices"]
            )
            for item in data
        }
