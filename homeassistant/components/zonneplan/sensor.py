"""Sensor platform for Zonneplan."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from aiozoneinfo import get_time_zone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
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


@dataclass(frozen=True, kw_only=True)
class ZonneplanPriceSensorEntityDescription(SensorEntityDescription):
    """Describes a Zonneplan price sensor."""

    value_fn: Callable[[ZonneplanCoordinator], float | str | datetime | None]
    supported_fn: Callable[[ZonneplanCoordinator], bool] | None = None


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
                        for electricity_prices in (coordinator.data.electricity_prices,)
                        if electricity_prices is not None
                        for point in electricity_prices.prices
                        if point.start_date <= dt_util.utcnow() < point.end_date
                    ),
                    None,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="lowest_electricity_price_today",
        translation_key="lowest_electricity_price_today",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if coordinator.data.electricity_prices is not None
            and (
                point := coordinator.data.electricity_prices.extreme_price(
                    dt_util.now(ZONNEPLAN_TIMEZONE).date(),
                    ZONNEPLAN_TIMEZONE,
                    lowest=True,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="highest_electricity_price_today",
        translation_key="highest_electricity_price_today",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if coordinator.data.electricity_prices is not None
            and (
                point := coordinator.data.electricity_prices.extreme_price(
                    dt_util.now(ZONNEPLAN_TIMEZONE).date(),
                    ZONNEPLAN_TIMEZONE,
                    lowest=False,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="lowest_electricity_price_tomorrow",
        translation_key="lowest_electricity_price_tomorrow",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if coordinator.data.electricity_prices is not None
            and (
                point := coordinator.data.electricity_prices.extreme_price(
                    dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1),
                    ZONNEPLAN_TIMEZONE,
                    lowest=True,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="highest_electricity_price_tomorrow",
        translation_key="highest_electricity_price_tomorrow",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if coordinator.data.electricity_prices is not None
            and (
                point := coordinator.data.electricity_prices.extreme_price(
                    dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1),
                    ZONNEPLAN_TIMEZONE,
                    lowest=False,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="electricity_prices_tomorrow_status",
        translation_key="electricity_prices_tomorrow_status",
        device_class=SensorDeviceClass.ENUM,
        options=["incoming", "available"],
        value_fn=lambda coordinator: (
            "available"
            if coordinator.data.electricity_prices is not None
            and coordinator.data.electricity_prices.prices_for_day(
                dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1),
                ZONNEPLAN_TIMEZONE,
            )
            else "incoming"
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="gas_price_today",
        translation_key="gas_price_today",
        native_unit_of_measurement=f"EUR/{UnitOfVolume.CUBIC_METERS}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if coordinator.data.gas_prices is not None
            and (
                point := next(
                    iter(
                        coordinator.data.gas_prices.prices_for_day(
                            dt_util.now(ZONNEPLAN_TIMEZONE).date(), ZONNEPLAN_TIMEZONE
                        )
                    ),
                    None,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.gas_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="electricity_price_low_today_start_time",
        translation_key="electricity_price_low_today_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda coordinator: (
            dt_util.as_local(block[0].start_date)
            if coordinator.data.electricity_prices is not None
            and (
                block := coordinator.data.electricity_prices.price_block(
                    dt_util.now(ZONNEPLAN_TIMEZONE).date(),
                    ZONNEPLAN_TIMEZONE,
                    lowest=True,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="electricity_price_low_today_end_time",
        translation_key="electricity_price_low_today_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda coordinator: (
            dt_util.as_local(block[1].end_date)
            if coordinator.data.electricity_prices is not None
            and (
                block := coordinator.data.electricity_prices.price_block(
                    dt_util.now(ZONNEPLAN_TIMEZONE).date(),
                    ZONNEPLAN_TIMEZONE,
                    lowest=True,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="electricity_price_low_tomorrow_start_time",
        translation_key="electricity_price_low_tomorrow_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda coordinator: (
            dt_util.as_local(block[0].start_date)
            if coordinator.data.electricity_prices is not None
            and (
                block := coordinator.data.electricity_prices.price_block(
                    dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1),
                    ZONNEPLAN_TIMEZONE,
                    lowest=True,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="electricity_price_low_tomorrow_end_time",
        translation_key="electricity_price_low_tomorrow_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda coordinator: (
            dt_util.as_local(block[1].end_date)
            if coordinator.data.electricity_prices is not None
            and (
                block := coordinator.data.electricity_prices.price_block(
                    dt_util.now(ZONNEPLAN_TIMEZONE).date() + timedelta(days=1),
                    ZONNEPLAN_TIMEZONE,
                    lowest=True,
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
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
    def native_value(self) -> StateType | datetime:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator)
