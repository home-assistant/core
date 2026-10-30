"""Bitcoin information service that uses blockchain.com."""

import logging
from typing import override

import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_CURRENCY, CONF_DISPLAY_OPTIONS, UnitOfTime
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DEFAULT_CURRENCY, DOMAIN, INTEGRATION_TITLE
from .coordinator import BitcoinConfigEntry, BitcoinDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

BREAKS_IN_HA_VERSION = "2027.4.0"

PARALLEL_UPDATES = 0

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="exchangerate",
        translation_key="exchangerate",
    ),
    SensorEntityDescription(
        key="trade_volume_btc",
        translation_key="trade_volume_btc",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="miners_revenue_usd",
        translation_key="miners_revenue_usd",
        native_unit_of_measurement="USD",
    ),
    SensorEntityDescription(
        key="btc_mined",
        translation_key="btc_mined",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="trade_volume_usd",
        translation_key="trade_volume_usd",
        native_unit_of_measurement="USD",
    ),
    SensorEntityDescription(
        key="difficulty",
        translation_key="difficulty",
    ),
    SensorEntityDescription(
        key="minutes_between_blocks",
        translation_key="minutes_between_blocks",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="number_of_transactions",
        translation_key="number_of_transactions",
    ),
    SensorEntityDescription(
        key="hash_rate",
        translation_key="hash_rate",
        native_unit_of_measurement=f"PH/{UnitOfTime.SECONDS}",
    ),
    SensorEntityDescription(
        key="timestamp",
        translation_key="timestamp",
    ),
    SensorEntityDescription(
        key="mined_blocks",
        translation_key="mined_blocks",
    ),
    SensorEntityDescription(
        key="blocks_size",
        translation_key="blocks_size",
    ),
    SensorEntityDescription(
        key="total_fees_btc",
        translation_key="total_fees_btc",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="total_btc_sent",
        translation_key="total_btc_sent",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="estimated_btc_sent",
        translation_key="estimated_btc_sent",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="total_btc",
        translation_key="total_btc",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="total_blocks",
        translation_key="total_blocks",
    ),
    SensorEntityDescription(
        key="next_retarget",
        translation_key="next_retarget",
    ),
    SensorEntityDescription(
        key="estimated_transaction_volume_usd",
        translation_key="estimated_transaction_volume_usd",
        native_unit_of_measurement="USD",
    ),
    SensorEntityDescription(
        key="miners_revenue_btc",
        translation_key="miners_revenue_btc",
        native_unit_of_measurement="BTC",
    ),
    SensorEntityDescription(
        key="market_price_usd",
        translation_key="market_price_usd",
        native_unit_of_measurement="USD",
    ),
)

OPTION_KEYS = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_DISPLAY_OPTIONS, default=[]): probatio.All(
            probatio.EnsureList(), [probatio.In(OPTION_KEYS)]
        ),
        probatio.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): cv.string,
    }
)


@callback
def _async_create_import_issue(
    hass: HomeAssistant, issue_id: str, translation_key: str, currency: str
) -> None:
    """Tell the user why a YAML sensor platform block was not imported."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        # The currency comes straight from YAML, so keep it out of the issue ID.
        f"deprecated_yaml_import_issue_{slugify(issue_id)}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{translation_key}",
        translation_placeholders={
            "currency": currency,
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML sensor platform into a config entry."""
    currency = config[CONF_CURRENCY].upper()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )

    if result["type"] is FlowResultType.ABORT:
        reason = result["reason"]
        if reason != "single_instance_allowed":
            _async_create_import_issue(hass, f"{reason}_{currency}", reason, currency)
            return

        # Only one entry is allowed, so a second block asking for another
        # currency is dropped. Say so instead of reporting a clean import.
        # Ignored entries also abort the flow, and those carry no currency.
        entries = hass.config_entries.async_entries(DOMAIN, include_ignore=False)
        if entries and entries[0].data[CONF_CURRENCY] != currency:
            _async_create_import_issue(
                hass, f"dropped_currency_{currency}", "dropped_currency", currency
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
    entry: BitcoinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bitcoin sensors from a config entry."""
    coordinator = entry.runtime_data

    currency = entry.data[CONF_CURRENCY]
    if currency not in coordinator.data.ticker:
        _LOGGER.warning("Currency %s is not available. Using USD", currency)

    async_add_entities(
        BitcoinSensor(coordinator, currency, description)
        for description in SENSOR_TYPES
    )


class BitcoinSensor(CoordinatorEntity[BitcoinDataUpdateCoordinator], SensorEntity):
    """Representation of a Bitcoin sensor."""

    _attr_attribution = "Data provided by blockchain.com"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BitcoinDataUpdateCoordinator,
        currency: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Blockchain.com",
            name=INTEGRATION_TITLE,
            configuration_url="https://www.blockchain.com/explorer",
        )
        self._currency = currency
        self._update_from_data()

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_data()
        super()._handle_coordinator_update()

    def _update_from_data(self) -> None:
        """Set the state from the latest coordinator data."""
        stats = self.coordinator.data.stats
        ticker = self.coordinator.data.ticker

        sensor_type = self.entity_description.key
        if sensor_type == "exchangerate":
            # The coordinator makes sure USD is quoted whenever this is not.
            currency = self._currency if self._currency in ticker else DEFAULT_CURRENCY
            self._attr_native_value = ticker[currency].p15min
            self._attr_native_unit_of_measurement = currency
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
