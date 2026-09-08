"""Coordinator for the Fuelprices.dk integration."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from aiohttp import ClientResponseError
from pybraendstofpriser import Braendstofpriser
from pybraendstofpriser.exceptions import ProductNotFoundError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from . import FuelpricesDkConfigEntry

SCAN_INTERVAL = timedelta(hours=1)

_LOGGER = logging.getLogger(__name__)


class FuelPricesDKCoordinator(DataUpdateCoordinator[dict[str, float | None]]):
    """Data update coordinator for the Fuelprices.dk integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        company: str,
        station: dict[str, Any],
        subentry_id: str,
        config_entry: FuelpricesDkConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            name=company,
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

        self._api = Braendstofpriser(api_key)
        self.company = company
        self.station_id: int = station["id"]
        self.station_name: str = station["name"]
        self.subentry_id = subentry_id

    @override
    async def _async_update_data(self) -> dict[str, float | None]:
        """Handle data update request from the coordinator."""
        try:
            data = await self._api.get_prices(self.station_id)
        except ProductNotFoundError as exc:
            raise ConfigEntryError(exc) from exc
        except ClientResponseError as exc:
            if exc.status == 401:
                raise ConfigEntryAuthFailed(exc) from exc
            raise ConfigEntryError(exc) from exc

        self.station_name = data["station"]["name"]

        return dict(data["prices"])
