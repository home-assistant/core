"""Bitcoin information service that uses blockchain.com."""
from datetime import timedelta
import logging

from blockchain import exchangerates, statistics
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_CURRENCY,
    CONF_DISPLAY_OPTIONS,
    TIME_MINUTES,
    TIME_SECONDS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by blockchain.com"

DEFAULT_CURRENCY = "USD"

ICON = "mdi:currency-btc"

SCAN_INTERVAL = timedelta(minutes=5)

OPTION_TYPES = {
    "exchangerate": ["Exchange rate (1 BTC)", None],
    "trade_volume_btc": ["Trade volume", "BTC"],
    "miners_revenue_usd": ["Miners revenue", "USD"],
    "btc_mined": ["Mined", "BTC"],
    "trade_volume_usd": ["Trade volume", "USD"],
    "difficulty": ["Difficulty", None],
    "minutes_between_blocks": ["Time between Blocks", TIME_MINUTES],
    "number_of_transactions": ["No. of Transactions", None],
    "hash_rate": ["Hash rate", f"PH/{TIME_SECONDS}"],
    "timestamp": ["Timestamp", None],
    "mined_blocks": ["Mined Blocks", None],
    "blocks_size": ["Block size", None],
    "total_fees_btc": ["Total fees", "BTC"],
    "total_btc_sent": ["Total sent", "BTC"],
    "estimated_btc_sent": ["Estimated sent", "BTC"],
    "total_btc": ["Total", "BTC"],
    "total_blocks": ["Total Blocks", None],
    "next_retarget": ["Next retarget", None],
    "estimated_transaction_volume_usd": ["Est. Transaction volume", "USD"],
    "miners_revenue_btc": ["Miners revenue", "BTC"],
    "market_price_usd": ["Market price", "USD"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DISPLAY_OPTIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(OPTION_TYPES)]
        ),
        vol.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Bitcoin sensors."""

    currency = config.get(CONF_CURRENCY)

    if currency not in exchangerates.get_ticker():
        _LOGGER.warning("Currency %s is not available. Using USD", currency)
        currency = DEFAULT_CURRENCY

    data = BitcoinData()
    dev = []
    for variable in config[CONF_DISPLAY_OPTIONS]:
        dev.append(BitcoinSensor(data, variable, currency))

    add_entities(dev, True)


class BitcoinSensor(Entity):
    """Representation of a Bitcoin sensor."""

    def __init__(self, data, option_type, currency):
        """Initialize the sensor."""
        self.data = data
        self._name = OPTION_TYPES[option_type][0]
        self._unit_of_measurement = OPTION_TYPES[option_type][1]
        self._currency = currency
        self.type = option_type
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        stats = self.data.stats
        ticker = self.data.ticker

        if self.type == "exchangerate":
            self._state = ticker[self._currency].p15min
            self._unit_of_measurement = self._currency
        elif self.type == "trade_volume_btc":
            self._state = f"{stats.trade_volume_btc:.1f}"
        elif self.type == "miners_revenue_usd":
            self._state = f"{stats.miners_revenue_usd:.0f}"
        elif self.type == "btc_mined":
            self._state = str(stats.btc_mined * 0.00000001)
        elif self.type == "trade_volume_usd":
            self._state = f"{stats.trade_volume_usd:.1f}"
        elif self.type == "difficulty":
            self._state = f"{stats.difficulty:.0f}"
        elif self.type == "minutes_between_blocks":
            self._state = f"{stats.minutes_between_blocks:.2f}"
        elif self.type == "number_of_transactions":
            self._state = str(stats.number_of_transactions)
        elif self.type == "hash_rate":
            self._state = f"{stats.hash_rate * 0.000001:.1f}"
        elif self.type == "timestamp":
            self._state = stats.timestamp
        elif self.type == "mined_blocks":
            self._state = str(stats.mined_blocks)
        elif self.type == "blocks_size":
            self._state = f"{stats.blocks_size:.1f}"
        elif self.type == "total_fees_btc":
            self._state = f"{stats.total_fees_btc * 0.00000001:.2f}"
        elif self.type == "total_btc_sent":
            self._state = f"{stats.total_btc_sent * 0.00000001:.2f}"
        elif self.type == "estimated_btc_sent":
            self._state = f"{stats.estimated_btc_sent * 0.00000001:.2f}"
        elif self.type == "total_btc":
            self._state = f"{stats.total_btc * 0.00000001:.2f}"
        elif self.type == "total_blocks":
            self._state = f"{stats.total_blocks:.0f}"
        elif self.type == "next_retarget":
            self._state = f"{stats.next_retarget:.2f}"
        elif self.type == "estimated_transaction_volume_usd":
            self._state = f"{stats.estimated_transaction_volume_usd:.2f}"
        elif self.type == "miners_revenue_btc":
            self._state = f"{stats.miners_revenue_btc * 0.00000001:.1f}"
        elif self.type == "market_price_usd":
            self._state = f"{stats.market_price_usd:.2f}"


class BitcoinData:
    """Get the latest data and update the states."""

    def __init__(self):
        """Initialize the data object."""
        self.stats = None
        self.ticker = None

    def update(self):
        """Get the latest data from blockchain.com."""

        self.stats = statistics.get()
        self.ticker = exchangerates.get_ticker()
