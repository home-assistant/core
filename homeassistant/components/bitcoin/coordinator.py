"""Data update coordinator for the Bitcoin integration."""

from dataclasses import dataclass
import logging
from typing import override

from blockchain import exchangerates, statistics
from blockchain.exceptions import APIException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CURRENCY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

API_ERRORS = (APIException, OSError, ValueError)

type BitcoinConfigEntry = ConfigEntry[BitcoinDataUpdateCoordinator]


@dataclass(slots=True)
class BitcoinData:
    """Network statistics plus the rate of the currency the user picked."""

    stats: statistics.Stats
    exchange_rate: float


def get_currencies() -> list[str]:
    """Return the currency codes blockchain.com quotes Bitcoin in."""
    return sorted(exchangerates.get_ticker())


class BitcoinDataUpdateCoordinator(DataUpdateCoordinator[BitcoinData]):
    """Coordinator that polls blockchain.com."""

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
        self.currency: str = config_entry.data[CONF_CURRENCY]

    def _fetch(self) -> BitcoinData:
        """Fetch statistics and the exchange rate ticker."""
        try:
            stats = statistics.get()
            ticker = exchangerates.get_ticker()
        except API_ERRORS as err:
            raise UpdateFailed(f"Cannot reach blockchain.com: {err}") from err

        if (currency := ticker.get(self.currency)) is None:
            raise UpdateFailed(
                f"blockchain.com no longer quotes Bitcoin in {self.currency}"
            )

        return BitcoinData(stats=stats, exchange_rate=currency.p15min)

    @override
    async def _async_update_data(self) -> BitcoinData:
        """Get the latest data from blockchain.com."""
        return await self.hass.async_add_executor_job(self._fetch)
