"""The Bitcoin integration."""

from datetime import timedelta

from blockchain import exchangerates, statistics
from blockchain.exceptions import APIException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CURRENCY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import Throttle

from .const import DEFAULT_CURRENCY

PLATFORMS = [Platform.SENSOR]

API_ERRORS = (APIException, OSError, ValueError)

# Every sensor polls on its own, so without this each cycle would hit
# blockchain.com once per sensor instead of once in total.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

type BitcoinConfigEntry = ConfigEntry[BitcoinData]


class BitcoinData:
    """Get the latest data and update the states."""

    stats: statistics.Stats
    ticker: dict[str, exchangerates.Currency]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data from blockchain.com."""

        self.stats = statistics.get()
        self.ticker = exchangerates.get_ticker()


async def async_setup_entry(hass: HomeAssistant, entry: BitcoinConfigEntry) -> bool:
    """Set up Bitcoin from a config entry."""
    data = BitcoinData()
    try:
        await hass.async_add_executor_job(data.update)
    except API_ERRORS as err:
        raise ConfigEntryNotReady(f"Cannot reach blockchain.com: {err}") from err

    # The exchange rate sensor falls back to USD, so USD only has to be quoted
    # when the currency the user picked is missing.
    currency = entry.data[CONF_CURRENCY]
    if currency not in data.ticker and DEFAULT_CURRENCY not in data.ticker:
        raise ConfigEntryNotReady(f"blockchain.com quotes neither {currency} nor USD")

    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BitcoinConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
