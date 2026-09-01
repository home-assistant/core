"""Bitcoin information service that uses blockchain.com."""

from datetime import timedelta
import logging

from blockchain import exchangerates, statistics
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_CURRENCY, CONF_DISPLAY_OPTIONS, UnitOfTime
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from .config_flow import API_ERRORS
from .const import DEFAULT_CURRENCY, DOMAIN, INTEGRATION_TITLE

_LOGGER = logging.getLogger(__name__)

BREAKS_IN_HA_VERSION = "2027.4.0"

SCAN_INTERVAL = timedelta(minutes=5)

# Every sensor polls on its own, so without this each cycle would hit
# blockchain.com once per sensor instead of once in total.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

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
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="number_of_transactions",
        name="No. of Transactions",
    ),
    SensorEntityDescription(
        key="hash_rate",
        name="Hash rate",
        native_unit_of_measurement=f"PH/{UnitOfTime.SECONDS}",
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

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DISPLAY_OPTIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(OPTION_KEYS)]
        ),
        vol.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML sensor platform into a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )

    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "single_instance_allowed"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version=BREAKS_IN_HA_VERSION,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders={
                "currency": config[CONF_CURRENCY],
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bitcoin sensors from a config entry."""
    data = BitcoinData()
    try:
        await hass.async_add_executor_job(data.update)
    except API_ERRORS as err:
        raise PlatformNotReady(f"Cannot reach blockchain.com: {err}") from err

    currency = entry.data[CONF_CURRENCY]
    if currency not in data.ticker:
        _LOGGER.warning("Currency %s is not available. Using USD", currency)
        currency = DEFAULT_CURRENCY

    async_add_entities(
        (BitcoinSensor(data, currency, description) for description in SENSOR_TYPES),
        True,
    )


class BitcoinSensor(SensorEntity):
    """Representation of a Bitcoin sensor."""

    _attr_attribution = "Data provided by blockchain.com"
    _attr_icon = "mdi:currency-btc"

    def __init__(
        self, data: BitcoinData, currency: str, description: SensorEntityDescription
    ) -> None:
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
            self._attr_native_value = str(stats.btc_mined * 1e-8)
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
            self._attr_native_value = f"{stats.total_fees_btc * 1e-8:.2f}"
        elif sensor_type == "total_btc_sent":
            self._attr_native_value = f"{stats.total_btc_sent * 1e-8:.2f}"
        elif sensor_type == "estimated_btc_sent":
            self._attr_native_value = f"{stats.estimated_btc_sent * 1e-8:.2f}"
        elif sensor_type == "total_btc":
            self._attr_native_value = f"{stats.total_btc * 1e-8:.2f}"
        elif sensor_type == "total_blocks":
            self._attr_native_value = f"{stats.total_blocks:.0f}"
        elif sensor_type == "next_retarget":
            self._attr_native_value = f"{stats.next_retarget:.2f}"
        elif sensor_type == "estimated_transaction_volume_usd":
            self._attr_native_value = f"{stats.estimated_transaction_volume_usd:.2f}"
        elif sensor_type == "miners_revenue_btc":
            self._attr_native_value = f"{stats.miners_revenue_btc * 1e-8:.1f}"
        elif sensor_type == "market_price_usd":
            self._attr_native_value = f"{stats.market_price_usd:.2f}"


class BitcoinData:
    """Get the latest data and update the states."""

    stats: statistics.Stats
    ticker: dict[str, exchangerates.Currency]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data from blockchain.com."""

        self.stats = statistics.get()
        self.ticker = exchangerates.get_ticker()
