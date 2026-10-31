"""Data update coordinator for the Bitcoin integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from blockchain import exchangerates, statistics
from blockchain.exceptions import APIException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CURRENCY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_CURRENCY, DOMAIN

_LOGGER = logging.getLogger(__name__)

API_ERRORS = (APIException, OSError, ValueError)

SCAN_INTERVAL = timedelta(minutes=5)

type BitcoinConfigEntry = ConfigEntry[BitcoinDataUpdateCoordinator]


@dataclass(slots=True)
class BitcoinData:
    """Network statistics and the exchange rate ticker."""

    stats: statistics.Stats
    ticker: dict[str, exchangerates.Currency]


class BitcoinDataUpdateCoordinator(DataUpdateCoordinator[BitcoinData]):
    """Coordinator that fetches everything from blockchain.com once per cycle."""

    config_entry: BitcoinConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: BitcoinConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def _fetch(self) -> BitcoinData:
        """Fetch the statistics and the exchange rate ticker."""
        try:
            stats = statistics.get()
            ticker = exchangerates.get_ticker()
        except API_ERRORS as err:
            raise UpdateFailed(f"Cannot reach blockchain.com: {err}") from err

        # The exchange rate sensor falls back to USD, so USD only has to be
        # quoted when the currency the user picked is missing.
        currency = self.config_entry.data[CONF_CURRENCY]
        if currency not in ticker and DEFAULT_CURRENCY not in ticker:
            raise UpdateFailed(f"blockchain.com quotes neither {currency} nor USD")

        return BitcoinData(stats=stats, ticker=ticker)

    @override
    async def _async_update_data(self) -> BitcoinData:
        """Get the latest data from blockchain.com."""
        return await self.hass.async_add_executor_job(self._fetch)
