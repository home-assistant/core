"""Sensor platform for Zonneplan."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import override

from aiozoneinfo import get_time_zone
from pyzonneplan import PricePoint

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import ZonneplanConfigEntry, ZonneplanCoordinator
from .entity import ZonneplanEntity

PARALLEL_UPDATES = 0

# It's for Dutchies, so ya...
ZONNEPLAN_TIMEZONE = get_time_zone("Europe/Amsterdam")


def _extreme_price_for_day(
    coordinator: ZonneplanCoordinator, day: date, *, lowest: bool
) -> PricePoint | None:
    prices = [
        point
        for point in coordinator.data.electricity_prices.prices
        if point.start_date.astimezone(ZONNEPLAN_TIMEZONE).date() == day
    ]

    if lowest:
        return min(
            prices, key=lambda point: point.price_tax_included.amount, default=None
        )
    return max(prices, key=lambda point: point.price_tax_included.amount, default=None)


def _price_block_for_day(
    coordinator: ZonneplanCoordinator, day: date, *, lowest: bool
) -> tuple[PricePoint, PricePoint] | None:
    """Return the bounds of the block of hours around the day's extreme price."""
    extreme = _extreme_price_for_day(coordinator, day, lowest=lowest)
    if extreme is None:
        return None

    prices = sorted(
        (
            point
            for point in coordinator.data.electricity_prices.prices
            if point.start_date.astimezone(ZONNEPLAN_TIMEZONE).date() == day
        ),
        key=lambda point: point.start_date,
    )
    extreme_amount = extreme.price_tax_included.amount
    # Groups hours of the day's extreme price
    # The idea is that automations can act on the whole block
    # Not on one hour
    max_deviation = abs(extreme_amount) * 0.05

    def _in_block(point: PricePoint) -> bool:
        return abs(point.price_tax_included.amount - extreme_amount) <= max_deviation

    index = prices.index(extreme)
    start = index
    while start > 0 and _in_block(prices[start - 1]):
        start -= 1
    end = index
    while end < len(prices) - 1 and _in_block(prices[end + 1]):
        end += 1

    return prices[start], prices[end]


def _price_attrs(
    coordinator: ZonneplanCoordinator, day: date, *, lowest: bool
) -> dict[str, str] | None:
    block = _price_block_for_day(coordinator, day, lowest=lowest)
    if block is None:
        return None
    block_start, block_end = block
    return {
        "start": dt_util.as_local(block_start.start_date).isoformat(),
        "end": dt_util.as_local(block_end.end_date).isoformat(),
    }


@dataclass(frozen=True, kw_only=True)
class ZonneplanPriceSensorEntityDescription(SensorEntityDescription):
    """Describes a Zonneplan price sensor."""

    value_fn: Callable[[ZonneplanCoordinator], float | str | None]
    attrs_fn: Callable[[ZonneplanCoordinator], dict[str, str] | None]


ZONNEPLAN_SENSORS: tuple[ZonneplanPriceSensorEntityDescription, ...] = (
    ZonneplanPriceSensorEntityDescription(
        key="current_electricity_price",
        translation_key="current_electricity_price",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if (
                point := next(
                    (
                        point
                        for point in coordinator.data.electricity_prices.prices
                        if point.start_date <= dt_util.utcnow() < point.end_date
                    ),
                    None,
                )
            )
            else None
        ),
        attrs_fn=lambda _: None,
    ),
    ZonneplanPriceSensorEntityDescription(
        key="lowest_electricity_price_today",
        translation_key="lowest_electricity_price_today",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if (
                point := _extreme_price_for_day(
                    coordinator, dt_util.now(ZONNEPLAN_TIMEZONE).date(), lowest=True
                )
            )
            else None
        ),
        attrs_fn=lambda coordinator: _price_attrs(
            coordinator, dt_util.now(ZONNEPLAN_TIMEZONE).date(), lowest=True
        ),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="highest_electricity_price_today",
        translation_key="highest_electricity_price_today",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if (
                point := _extreme_price_for_day(
                    coordinator, dt_util.now(ZONNEPLAN_TIMEZONE).date(), lowest=False
                )
            )
            else None
        ),
        attrs_fn=lambda coordinator: _price_attrs(
            coordinator, dt_util.now(ZONNEPLAN_TIMEZONE).date(), lowest=False
        ),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="lowest_electricity_price_tomorrow",
        translation_key="lowest_electricity_price_tomorrow",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if (
                point := _extreme_price_for_day(
                    coordinator,
                    dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1),
                    lowest=True,
                )
            )
            else None
        ),
        attrs_fn=lambda coordinator: _price_attrs(
            coordinator,
            dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1),
            lowest=True,
        ),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="highest_electricity_price_tomorrow",
        translation_key="highest_electricity_price_tomorrow",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if (
                point := _extreme_price_for_day(
                    coordinator,
                    dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1),
                    lowest=False,
                )
            )
            else None
        ),
        attrs_fn=lambda coordinator: _price_attrs(
            coordinator,
            dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1),
            lowest=False,
        ),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="electricity_prices_tomorrow_status",
        translation_key="electricity_prices_tomorrow_status",
        device_class=SensorDeviceClass.ENUM,
        options=["incoming", "available"],
        value_fn=lambda coordinator: (
            "available"
            if any(
                point.start_date.astimezone(ZONNEPLAN_TIMEZONE).date()
                == dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1)
                for point in coordinator.data.electricity_prices.prices
            )
            else "incoming"
        ),
        attrs_fn=lambda _: None,
    ),
    ZonneplanPriceSensorEntityDescription(
        key="gas_price_today",
        translation_key="gas_price_today",
        native_unit_of_measurement=f"EUR/{UnitOfVolume.CUBIC_METERS}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if (
                point := next(
                    (
                        point
                        for point in coordinator.data.gas_prices.prices
                        if point.start_date.astimezone(ZONNEPLAN_TIMEZONE).date()
                        == dt_util.now(ZONNEPLAN_TIMEZONE).date()
                    ),
                    None,
                )
            )
            else None
        ),
        attrs_fn=lambda _: None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZonneplanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zonneplan sensor platform."""
    coordinator = entry.runtime_data

    async_add_entities(
        ZonneplanPriceSensor(coordinator, description)
        for description in ZONNEPLAN_SENSORS
    )


class ZonneplanPriceSensor(ZonneplanEntity, SensorEntity):
    """Representation of a Zonneplan electricity price sensor."""

    entity_description: ZonneplanPriceSensorEntityDescription

    @property
    @override
    def native_value(self) -> float | str | None:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the extra state attributes."""
        return self.entity_description.attrs_fn(self.coordinator)
