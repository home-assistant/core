"""Bitcoin information service that uses blockchain.com."""
from __future__ import annotations

from datetime import timedelta
import logging

from blockchain import exchangerates, statistics
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_CURRENCY,
    CONF_DISPLAY_OPTIONS,
    TIME_MINUTES,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by blockchain.com"

DEFAULT_CURRENCY = "USD"

ICON = "mdi:currency-btc"

SCAN_INTERVAL = timedelta(minutes=5)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="exchangerate",
        name="Exchange rate (1 BTC)",
    ),
    SensorEntityDescription(
        key="trade_volume_btc",
        name="Trade volume",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="miners_revenue_usd",
        name="Miners revenue",
        native_unit_of_measurement="USD",
    ),
    SensorEntityDescription(
        key="btc_mined",
        name="Mined",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="trade_volume_usd",
        name="Trade volume",
        native_unit_of_measurement="USD",
    ),
    SensorEntityDescription(
        key="difficulty",
        name="Difficulty",
    ),
    SensorEntityDescription(
        key="minutes_between_blocks",
        name="Time between Blocks",
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key="number_of_transactions",
        name="No. of Transactions",
    ),
    SensorEntityDescription(
        key="hash_rate",
        name="Hash rate",
        native_unit_of_measurement=f"PH/{TIME_SECONDS}",
    ),
    SensorEntityDescription(
        key="timestamp",
        name="Timestamp",
    ),
    SensorEntityDescription(
        key="mined_blocks",
        name="Mined Blocks",
    ),
    SensorEntityDescription(
        key="blocks_size",
        name="Block size",
    ),
    SensorEntityDescription(
        key="total_fees_btc",
        name="Total fees",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="total_btc_sent",
        name="Total sent",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="estimated_btc_sent",
        name="Estimated sent",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="total_btc",
        name="Total",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="total_blocks",
        name="Total Blocks",
    ),
    SensorEntityDescription(
        key="next_retarget",
        name="Next retarget",
    ),
    SensorEntityDescription(
        key="estimated_transaction_volume_usd",
        name="Est. Transaction volume",
        native_unit_of_measurement="USD",
    ),
    SensorEntityDescription(
        key="miners_revenue_btc",
        name="Miners revenue",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="market_price_usd",
        name="Market price",
        native_unit_of_measurement="USD",
    ),
)

OPTION_KEYS = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DISPLAY_OPTIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(OPTION_KEYS)]
        ),
        vol.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Bitcoin sensors."""

    currency = config[CONF_CURRENCY]

    if currency not in exchangerates.get_ticker():
        _LOGGER.warning("Currency %s is not available. Using USD", currency)
        currency = DEFAULT_CURRENCY

    data = BitcoinData()
    entities = [
        BitcoinSensor(data, currency, description)
        for description in SENSOR_TYPES
        if description.key in config[CONF_DISPLAY_OPTIONS]
    ]

    add_entities(entities, True)


class BitcoinSensor(SensorEntity):
    """Representation of a Bitcoin sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = ICON

    def __init__(self, data, currency, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self.data = data
        self._currency = currency

    def update(self) -> None:
        """Get the latest data and updates the states."""
        self.data.update()
        stats = self.data.stats
        ticker = self.data.ticker

        sensor_type = self.entity_description.key
        if sensor_type == "exchangerate":
            self._attr_native_value = ticker[self._currency].p15min
            self._attr_native_unit_of_measurement = self._currency
        elif sensor_type == "trade_volume_btc":
            self._attr_native_value = f"{stats.trade_volume_btc:.1f}"
        elif sensor_type == "miners_revenue_usd":
            self._attr_native_value = f"{stats.miners_revenue_usd:.0f}"
        elif sensor_type == "btc_mined":
            self._attr_native_value = str(stats.btc_mined * 0.00000001)
        elif sensor_type == "trade_volume_usd":
            self._attr_native_value = f"{stats.trade_volume_usd:.1f}"
        elif sensor_type == "difficulty":
            self._attr_native_value = f"{stats.difficulty:.0f}"
        elif sensor_type == "minutes_between_blocks":
            self._attr_native_value = f"{stats.minutes_between_blocks:.2f}"
        elif sensor_type == "number_of_transactions":
            self._attr_native_value = str(stats.number_of_transactions)
        elif sensor_type == "hash_rate":
            self._attr_native_value = f"{stats.hash_rate * 0.000001:.1f}"
        elif sensor_type == "timestamp":
            self._attr_native_value = stats.timestamp
        elif sensor_type == "mined_blocks":
            self._attr_native_value = str(stats.mined_blocks)
        elif sensor_type == "blocks_size":
            self._attr_native_value = f"{stats.blocks_size:.1f}"
        elif sensor_type == "total_fees_btc":
            self._attr_native_value = f"{stats.total_fees_btc * 0.00000001:.2f}"
        elif sensor_type == "total_btc_sent":
            self._attr_native_value = f"{stats.total_btc_sent * 0.00000001:.2f}"
        elif sensor_type == "estimated_btc_sent":
            self._attr_native_value = f"{stats.estimated_btc_sent * 0.00000001:.2f}"
        elif sensor_type == "total_btc":
            self._attr_native_value = f"{stats.total_btc * 0.00000001:.2f}"
        elif sensor_type == "total_blocks":
            self._attr_native_value = f"{stats.total_blocks:.0f}"
        elif sensor_type == "next_retarget":
            self._attr_native_value = f"{stats.next_retarget:.2f}"
        elif sensor_type == "estimated_transaction_volume_usd":
            self._attr_native_value = f"{stats.estimated_transaction_volume_usd:.2f}"
        elif sensor_type == "miners_revenue_btc":
            self._attr_native_value = f"{stats.miners_revenue_btc * 0.00000001:.1f}"
        elif sensor_type == "market_price_usd":
            self._attr_native_value = f"{stats.market_price_usd:.2f}"


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
