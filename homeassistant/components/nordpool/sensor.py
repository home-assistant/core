"""Sensor platform for Nord Pool integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

from . import NordPoolConfigEntry
from .const import LOGGER
from .coordinator import NordPoolDataUpdateCoordinator
from .entity import NordpoolBaseEntity

PARALLEL_UPDATES = 0


def validate_prices(
    func: Callable[
        [NordpoolPriceSensor], dict[str, tuple[float | None, float, float | None]]
    ],
    entity: NordpoolPriceSensor,
    area: str,
    index: int,
) -> float | None:
    """Validate and return."""
    if result := func(entity)[area][index]:
        return result / 1000
    return None


def get_prices(
    entity: NordpoolPriceSensor,
) -> dict[str, tuple[float | None, float, float | None]]:
    """Return previous, current and next prices.

    Output: {"SE3": (10.0, 10.5, 12.1)}
    """
    data = entity.coordinator.merge_price_entries()
    last_price_entries: dict[str, float] = {}
    current_price_entries: dict[str, float] = {}
    next_price_entries: dict[str, float] = {}
    current_time = dt_util.utcnow()
    previous_time = current_time - timedelta(hours=1)
    next_time = current_time + timedelta(hours=1)
    LOGGER.debug("Price data: %s", data)
    for entry in data:
        if entry.start <= current_time <= entry.end:
            current_price_entries = entry.entry
        if entry.start <= previous_time <= entry.end:
            last_price_entries = entry.entry
        if entry.start <= next_time <= entry.end:
            next_price_entries = entry.entry
    LOGGER.debug(
        "Last price %s, current price %s, next price %s",
        last_price_entries,
        current_price_entries,
        next_price_entries,
    )

    result = {}
    for area, price in current_price_entries.items():
        result[area] = (
            last_price_entries.get(area),
            price,
            next_price_entries.get(area),
        )
    LOGGER.debug("Prices: %s", result)
    return result


def get_min_max_price(
    entity: NordpoolPriceSensor,
    func: Callable[[float, float], float],
) -> tuple[float, datetime, datetime]:
    """Get the lowest price from the data."""
    data = entity.coordinator.get_data_current_day()
    area = entity.area
    price_data = data.entries
    price: float = price_data[0].entry[area]
    start: datetime = price_data[0].start
    end: datetime = price_data[0].end
    for entry in price_data:
        for _area, _price in entry.entry.items():
            if _area == area and _price == func(price, _price):
                price = _price
                start = entry.start
                end = entry.end

    return (price, start, end)


def get_blockprices(
    entity: NordpoolBlockPriceSensor,
) -> dict[str, dict[str, tuple[datetime, datetime, float, float, float]]]:
    """Return average, min and max for block prices.

    Output: {"SE3": {"Off-peak 1": (_datetime_, _datetime_, 9.3, 10.5, 12.1)}}
    """
    data = entity.coordinator.get_data_current_day()
    result: dict[str, dict[str, tuple[datetime, datetime, float, float, float]]] = {}
    block_prices = data.block_prices
    for entry in block_prices:
        for _area in entry.average:
            if _area not in result:
                result[_area] = {}
            result[_area][entry.name] = (
                entry.start,
                entry.end,
                entry.average[_area]["average"],
                entry.average[_area]["min"],
                entry.average[_area]["max"],
            )

    LOGGER.debug("Block prices: %s", result)
    return result


@dataclass(frozen=True, kw_only=True)
class NordpoolDefaultSensorEntityDescription(SensorEntityDescription):
    """Describes Nord Pool default sensor entity."""

    value_fn: Callable[[NordpoolSensor], str | float | datetime | None]


@dataclass(frozen=True, kw_only=True)
class NordpoolPricesSensorEntityDescription(SensorEntityDescription):
    """Describes Nord Pool prices sensor entity."""

    value_fn: Callable[[NordpoolPriceSensor], float | None]
    extra_fn: Callable[[NordpoolPriceSensor], dict[str, str] | None]


@dataclass(frozen=True, kw_only=True)
class NordpoolBlockPricesSensorEntityDescription(SensorEntityDescription):
    """Describes Nord Pool block prices sensor entity."""

    value_fn: Callable[
        [tuple[datetime, datetime, float, float, float]], float | datetime | None
    ]


DEFAULT_SENSOR_TYPES: tuple[NordpoolDefaultSensorEntityDescription, ...] = (
    NordpoolDefaultSensorEntityDescription(
        key="updated_at",
        translation_key="updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda entity: entity.coordinator.get_data_current_day().updated_at,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NordpoolDefaultSensorEntityDescription(
        key="currency",
        translation_key="currency",
        value_fn=lambda entity: entity.coordinator.get_data_current_day().currency,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NordpoolDefaultSensorEntityDescription(
        key="exchange_rate",
        translation_key="exchange_rate",
        value_fn=lambda entity: entity.coordinator.get_data_current_day().exchange_rate,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)
PRICES_SENSOR_TYPES: tuple[NordpoolPricesSensorEntityDescription, ...] = (
    NordpoolPricesSensorEntityDescription(
        key="current_price",
        translation_key="current_price",
        value_fn=lambda entity: validate_prices(get_prices, entity, entity.area, 1),
        extra_fn=lambda entity: None,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    NordpoolPricesSensorEntityDescription(
        key="last_price",
        translation_key="last_price",
        value_fn=lambda entity: validate_prices(get_prices, entity, entity.area, 0),
        extra_fn=lambda entity: None,
        suggested_display_precision=2,
    ),
    NordpoolPricesSensorEntityDescription(
        key="next_price",
        translation_key="next_price",
        value_fn=lambda entity: validate_prices(get_prices, entity, entity.area, 2),
        extra_fn=lambda entity: None,
        suggested_display_precision=2,
    ),
    NordpoolPricesSensorEntityDescription(
        key="lowest_price",
        translation_key="lowest_price",
        value_fn=lambda entity: get_min_max_price(entity, min)[0] / 1000,
        extra_fn=lambda entity: {
            "start": get_min_max_price(entity, min)[1].isoformat(),
            "end": get_min_max_price(entity, min)[2].isoformat(),
        },
        suggested_display_precision=2,
    ),
    NordpoolPricesSensorEntityDescription(
        key="highest_price",
        translation_key="highest_price",
        value_fn=lambda entity: get_min_max_price(entity, max)[0] / 1000,
        extra_fn=lambda entity: {
            "start": get_min_max_price(entity, max)[1].isoformat(),
            "end": get_min_max_price(entity, max)[2].isoformat(),
        },
        suggested_display_precision=2,
    ),
)
BLOCK_PRICES_SENSOR_TYPES: tuple[NordpoolBlockPricesSensorEntityDescription, ...] = (
    NordpoolBlockPricesSensorEntityDescription(
        key="block_average",
        translation_key="block_average",
        value_fn=lambda data: data[2] / 1000,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    NordpoolBlockPricesSensorEntityDescription(
        key="block_min",
        translation_key="block_min",
        value_fn=lambda data: data[3] / 1000,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    NordpoolBlockPricesSensorEntityDescription(
        key="block_max",
        translation_key="block_max",
        value_fn=lambda data: data[4] / 1000,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    NordpoolBlockPricesSensorEntityDescription(
        key="block_start_time",
        translation_key="block_start_time",
        value_fn=lambda data: data[0],
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    NordpoolBlockPricesSensorEntityDescription(
        key="block_end_time",
        translation_key="block_end_time",
        value_fn=lambda data: data[1],
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
)
DAILY_AVERAGE_PRICES_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="daily_average",
        translation_key="daily_average",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NordPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nord Pool sensor platform."""

    coordinator = entry.runtime_data
    current_day_data = entry.runtime_data.get_data_current_day()

    entities: list[NordpoolBaseEntity] = []
    currency = current_day_data.currency

    for area in current_day_data.area_average:
        LOGGER.debug("Setting up base sensors for area %s", area)
        entities.extend(
            NordpoolSensor(coordinator, description, area)
            for description in DEFAULT_SENSOR_TYPES
        )
        LOGGER.debug(
            "Setting up price sensors for area %s with currency %s", area, currency
        )
        entities.extend(
            NordpoolPriceSensor(coordinator, description, area, currency)
            for description in PRICES_SENSOR_TYPES
        )
        entities.extend(
            NordpoolDailyAveragePriceSensor(coordinator, description, area, currency)
            for description in DAILY_AVERAGE_PRICES_SENSOR_TYPES
        )
        for block_prices in entry.runtime_data.get_data_current_day().block_prices:
            LOGGER.debug(
                "Setting up block price sensors for area %s with currency %s in block %s",
                area,
                currency,
                block_prices.name,
            )
            entities.extend(
                NordpoolBlockPriceSensor(
                    coordinator, description, area, currency, block_prices.name
                )
                for description in BLOCK_PRICES_SENSOR_TYPES
            )
    async_add_entities(entities)


class NordpoolSensor(NordpoolBaseEntity, SensorEntity):
    """Representation of a Nord Pool sensor."""

    entity_description: NordpoolDefaultSensorEntityDescription

    @property
    def native_value(self) -> str | float | datetime | None:
        """Return value of sensor."""
        return self.entity_description.value_fn(self)


class NordpoolPriceSensor(NordpoolBaseEntity, SensorEntity):
    """Representation of a Nord Pool price sensor."""

    entity_description: NordpoolPricesSensorEntityDescription

    def __init__(
        self,
        coordinator: NordPoolDataUpdateCoordinator,
        entity_description: NordpoolPricesSensorEntityDescription,
        area: str,
        currency: str,
    ) -> None:
        """Initiate Nord Pool sensor."""
        super().__init__(coordinator, entity_description, area)
        self._attr_native_unit_of_measurement = f"{currency}/kWh"

    @property
    def native_value(self) -> float | None:
        """Return value of sensor."""
        return self.entity_description.value_fn(self)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the extra state attributes."""
        return self.entity_description.extra_fn(self)


class NordpoolBlockPriceSensor(NordpoolBaseEntity, SensorEntity):
    """Representation of a Nord Pool block price sensor."""

    entity_description: NordpoolBlockPricesSensorEntityDescription

    def __init__(
        self,
        coordinator: NordPoolDataUpdateCoordinator,
        entity_description: NordpoolBlockPricesSensorEntityDescription,
        area: str,
        currency: str,
        block_name: str,
    ) -> None:
        """Initiate Nord Pool sensor."""
        super().__init__(coordinator, entity_description, area)
        if entity_description.device_class is not SensorDeviceClass.TIMESTAMP:
            self._attr_native_unit_of_measurement = f"{currency}/kWh"
        self._attr_unique_id = f"{slugify(block_name)}-{area}-{entity_description.key}"
        self.block_name = block_name
        self._attr_translation_placeholders = {"block": block_name}

    @property
    def native_value(self) -> float | datetime | None:
        """Return value of sensor."""
        return self.entity_description.value_fn(
            get_blockprices(self)[self.area][self.block_name]
        )


class NordpoolDailyAveragePriceSensor(NordpoolBaseEntity, SensorEntity):
    """Representation of a Nord Pool daily average price sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: NordPoolDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        area: str,
        currency: str,
    ) -> None:
        """Initiate Nord Pool sensor."""
        super().__init__(coordinator, entity_description, area)
        self._attr_native_unit_of_measurement = f"{currency}/kWh"

    @property
    def native_value(self) -> float | None:
        """Return value of sensor."""
        data = self.coordinator.get_data_current_day()
        return data.area_average[self.area] / 1000
