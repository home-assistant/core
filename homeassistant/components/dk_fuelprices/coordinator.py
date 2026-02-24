"""Coordinator for the dk_fuelprices integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from aiohttp import ClientResponseError
from pybraendstofpriser import Braendstofpriser
from pybraendstofpriser.exceptions import ProductNotFoundError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN

SCAN_INTERVAL = timedelta(hours=1)

_LOGGER = logging.getLogger(__name__)


class APIClient(DataUpdateCoordinator[None]):
    """DataUpdateCoordinator for Braendstofpriser."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        company: str,
        station: dict[str, Any],
        _products: dict[str, bool],
        subentry_id: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the API client."""
        super().__init__(
            hass=hass,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

        self._api = Braendstofpriser(api_key)
        self.company = company
        self.station_id: int = station["id"]
        self.station_name: str = station["name"]
        self.subentry_id = subentry_id
        self.products: dict[str, dict[str, str | float | None]] = {}
        self.updated_at: datetime | None = None

        self.name = self.company

    async def _async_setup(self) -> None:
        """Initialize the API client."""
        _LOGGER.debug("Initializing coordinator for station %s", self.station_id)

    async def _async_update_data(self) -> None:
        """Handle data update request from the coordinator."""
        try:
            data = await self._api.get_prices(self.station_id)
            self.station_name = data["station"]["name"]
            last_update = data["station"]["last_update"]
            if (
                last_update is None
                or (parsed_last_update := dt_util.parse_datetime(last_update)) is None
            ):
                self.updated_at = None
            elif parsed_last_update.tzinfo is None:
                self.updated_at = parsed_last_update.replace(tzinfo=dt_util.UTC)
            else:
                self.updated_at = dt_util.as_utc(parsed_last_update)

            # Expose every available product for the station.
            self.products = {
                product: {"name": product, "price": price}
                for product, price in data["prices"].items()
            }

            for product, product_data in self.products.items():
                _LOGGER.debug("Getting price for %s", product)
                _LOGGER.debug(
                    "Updated price for %s: %s",
                    product_data["name"],
                    product_data["price"],
                )
                _LOGGER.debug(
                    "Updated at: %s",
                    data["station"].get("last_update", "UNKNOWN"),
                )
        except ProductNotFoundError as exc:
            raise ConfigEntryError(exc) from exc
        except ClientResponseError as exc:
            if exc.status == 401:
                raise ConfigEntryAuthFailed(exc) from exc
            raise ConfigEntryError(exc) from exc
