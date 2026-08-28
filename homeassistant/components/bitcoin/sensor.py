"""Bitcoin information service that uses blockchain.com."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_CURRENCY,
    CONF_DISPLAY_OPTIONS,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DEFAULT_CURRENCY, DOMAIN, INTEGRATION_TITLE
from .coordinator import BitcoinConfigEntry, BitcoinData, BitcoinDataUpdateCoordinator

PARALLEL_UPDATES = 0

BREAKS_IN_HA_VERSION = "2027.4.0"

BTC = "BTC"
SATOSHI = 1e-8
USD = "USD"


@dataclass(frozen=True, kw_only=True)
class BitcoinSensorEntityDescription(SensorEntityDescription):
    """Describes a Bitcoin sensor."""

    value_fn: Callable[[BitcoinData], StateType | datetime]
    unit_from_currency: bool = False


SENSOR_TYPES: tuple[BitcoinSensorEntityDescription, ...] = (
    # No state class: reconfiguring the currency changes the unit, and
    # currencies are not convertible, which would break long term statistics.
    BitcoinSensorEntityDescription(
        key="exchangerate",
        translation_key="exchangerate",
        suggested_display_precision=2,
        unit_from_currency=True,
        value_fn=lambda data: data.exchange_rate,
    ),
    BitcoinSensorEntityDescription(
        key="trade_volume_btc",
        translation_key="trade_volume_btc",
        native_unit_of_measurement=BTC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.stats.trade_volume_btc,
    ),
    BitcoinSensorEntityDescription(
        key="miners_revenue_usd",
        translation_key="miners_revenue_usd",
        native_unit_of_measurement=USD,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.stats.miners_revenue_usd,
    ),
    BitcoinSensorEntityDescription(
        key="btc_mined",
        translation_key="btc_mined",
        native_unit_of_measurement=BTC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.stats.btc_mined * SATOSHI,
    ),
    BitcoinSensorEntityDescription(
        key="trade_volume_usd",
        translation_key="trade_volume_usd",
        native_unit_of_measurement=USD,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.stats.trade_volume_usd,
    ),
    BitcoinSensorEntityDescription(
        key="difficulty",
        translation_key="difficulty",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.stats.difficulty,
    ),
    BitcoinSensorEntityDescription(
        key="minutes_between_blocks",
        translation_key="minutes_between_blocks",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.stats.minutes_between_blocks,
    ),
    BitcoinSensorEntityDescription(
        key="number_of_transactions",
        translation_key="number_of_transactions",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.number_of_transactions,
    ),
    BitcoinSensorEntityDescription(
        key="hash_rate",
        translation_key="hash_rate",
        native_unit_of_measurement=f"PH/{UnitOfTime.SECONDS}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.stats.hash_rate * 1e-6,
    ),
    BitcoinSensorEntityDescription(
        key="timestamp",
        translation_key="timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: dt_util.utc_from_timestamp(data.stats.timestamp / 1000),
    ),
    BitcoinSensorEntityDescription(
        key="mined_blocks",
        translation_key="mined_blocks",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.mined_blocks,
    ),
    BitcoinSensorEntityDescription(
        key="blocks_size",
        translation_key="blocks_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.stats.blocks_size,
    ),
    BitcoinSensorEntityDescription(
        key="total_fees_btc",
        translation_key="total_fees_btc",
        native_unit_of_measurement=BTC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.stats.total_fees_btc * SATOSHI,
    ),
    BitcoinSensorEntityDescription(
        key="total_btc_sent",
        translation_key="total_btc_sent",
        native_unit_of_measurement=BTC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.stats.total_btc_sent * SATOSHI,
    ),
    BitcoinSensorEntityDescription(
        key="estimated_btc_sent",
        translation_key="estimated_btc_sent",
        native_unit_of_measurement=BTC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.stats.estimated_btc_sent * SATOSHI,
    ),
    BitcoinSensorEntityDescription(
        key="total_btc",
        translation_key="total_btc",
        native_unit_of_measurement=BTC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.stats.total_btc * SATOSHI,
    ),
    BitcoinSensorEntityDescription(
        key="total_blocks",
        translation_key="total_blocks",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.stats.total_blocks,
    ),
    BitcoinSensorEntityDescription(
        key="next_retarget",
        translation_key="next_retarget",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.next_retarget,
    ),
    BitcoinSensorEntityDescription(
        key="estimated_transaction_volume_usd",
        translation_key="estimated_transaction_volume_usd",
        native_unit_of_measurement=USD,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.stats.estimated_transaction_volume_usd,
    ),
    BitcoinSensorEntityDescription(
        key="miners_revenue_btc",
        translation_key="miners_revenue_btc",
        native_unit_of_measurement=BTC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.stats.miners_revenue_btc * SATOSHI,
    ),
    BitcoinSensorEntityDescription(
        key="market_price_usd",
        translation_key="market_price_usd",
        native_unit_of_measurement=USD,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.stats.market_price_usd,
    ),
)

OPTION_KEYS = [description.key for description in SENSOR_TYPES]

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
    entry: BitcoinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bitcoin sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        BitcoinSensor(coordinator, description) for description in SENSOR_TYPES
    )


class BitcoinSensor(CoordinatorEntity[BitcoinDataUpdateCoordinator], SensorEntity):
    """Representation of a Bitcoin sensor."""

    _attr_attribution = "Data provided by blockchain.com"
    _attr_has_entity_name = True

    entity_description: BitcoinSensorEntityDescription

    def __init__(
        self,
        coordinator: BitcoinDataUpdateCoordinator,
        description: BitcoinSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Blockchain.com",
            name=INTEGRATION_TITLE,
            configuration_url="https://www.blockchain.com/explorer",
        )
        if description.unit_from_currency:
            self._attr_native_unit_of_measurement = coordinator.currency

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
