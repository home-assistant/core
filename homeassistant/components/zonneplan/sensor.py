"""Sensor platform for Zonneplan."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from typing import override

from pyzonneplan import Battery, ElectricityChartGroup, GasChartGroup
from pyzonneplan.const import MONEY_FACTOR

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    CURRENCY_EURO,
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ZONNEPLAN_TIMEZONE
from .coordinator import (
    ZonneplanBatteryData,
    ZonneplanConfigEntry,
    ZonneplanCoordinator,
    ZonneplanData,
)
from .entity import ZonneplanBatteryEntity, ZonneplanEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

BATTERY_STATES = ["charging", "discharging", "operative"]


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
            if coordinator.data.electricity_prices is not None
            and (
                point := coordinator.data.electricity_prices.price_at(dt_util.utcnow())
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="next_hour_electricity_price",
        translation_key="next_hour_electricity_price",
        native_unit_of_measurement=f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: (
            float(point.price_tax_included.euro)
            if coordinator.data.electricity_prices is not None
            and (
                point := coordinator.data.electricity_prices.price_at(
                    dt_util.utcnow() + timedelta(hours=1)
                )
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="current_electricity_tariff_group",
        translation_key="current_electricity_tariff_group",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "normal", "high"],
        value_fn=lambda coordinator: (
            point.tariff_group
            if coordinator.data.electricity_prices is not None
            and (
                point := coordinator.data.electricity_prices.price_at(dt_util.utcnow())
            )
            else None
        ),
        supported_fn=lambda coordinator: bool(coordinator.data.electricity_prices),
    ),
    ZonneplanPriceSensorEntityDescription(
        key="current_sustainability_score",
        translation_key="current_sustainability_score",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda coordinator: (
            float(point.sustainability_score.fraction * 100)
            if coordinator.data.electricity_prices is not None
            and (
                point := coordinator.data.electricity_prices.price_at(dt_util.utcnow())
            )
            and point.sustainability_score is not None
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


@dataclass(frozen=True, kw_only=True)
class ZonneplanUsageSensorEntityDescription(SensorEntityDescription):
    """Describes a Zonneplan month-to-date usage sensor."""

    group_fn: Callable[[ZonneplanData], ElectricityChartGroup | GasChartGroup | None]
    value_fn: Callable[[ZonneplanData], Decimal | None]


ZONNEPLAN_USAGE_SENSORS: tuple[ZonneplanUsageSensorEntityDescription, ...] = (
    ZonneplanUsageSensorEntityDescription(
        key="electricity_delivered_this_month",
        translation_key="electricity_delivered_this_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        group_fn=lambda data: (
            data.electricity_usage.group if data.electricity_usage else None
        ),
        value_fn=lambda data: (
            group.delivered_kwh
            if data.electricity_usage and (group := data.electricity_usage.group)
            else None
        ),
    ),
    ZonneplanUsageSensorEntityDescription(
        key="electricity_produced_this_month",
        translation_key="electricity_produced_this_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        group_fn=lambda data: (
            data.electricity_usage.group if data.electricity_usage else None
        ),
        value_fn=lambda data: (
            group.produced_kwh
            if data.electricity_usage and (group := data.electricity_usage.group)
            else None
        ),
    ),
    ZonneplanUsageSensorEntityDescription(
        key="gas_delivered_this_month",
        translation_key="gas_delivered_this_month",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
        group_fn=lambda data: data.gas_usage.group if data.gas_usage else None,
        value_fn=lambda data: (
            group.total_m3
            if data.gas_usage and (group := data.gas_usage.group)
            else None
        ),
    ),
    ZonneplanUsageSensorEntityDescription(
        key="electricity_cost_this_month",
        translation_key="electricity_cost_this_month",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        group_fn=lambda data: (
            data.electricity_usage.group if data.electricity_usage else None
        ),
        value_fn=lambda data: (
            Decimal(str(group.meta["delivery_costs_incl_tax"])) * MONEY_FACTOR
            if data.electricity_usage
            and (group := data.electricity_usage.group)
            and group.has_data
            else None
        ),
    ),
    ZonneplanUsageSensorEntityDescription(
        key="gas_cost_this_month",
        translation_key="gas_cost_this_month",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        group_fn=lambda data: data.gas_usage.group if data.gas_usage else None,
        value_fn=lambda data: (
            Decimal(str(group.meta["delivery_costs_incl_tax"])) * MONEY_FACTOR
            if data.gas_usage and (group := data.gas_usage.group) and group.has_data
            else None
        ),
    ),
)


def _battery_state(state: str | None) -> str | None:
    """Return a battery or inverter state as an enum option."""
    if state is None:
        return None
    if (option := state.lower()) not in BATTERY_STATES:
        _LOGGER.debug("Unknown Zonneplan battery state: %s", state)
        return None
    return option


@dataclass(frozen=True, kw_only=True)
class ZonneplanBatterySensorEntityDescription(SensorEntityDescription):
    """Describes a Zonneplan home battery sensor."""

    value_fn: Callable[[Battery], StateType | Decimal]
    last_reset_fn: Callable[[ZonneplanBatteryData], datetime | None] | None = None


ZONNEPLAN_BATTERY_SENSORS: tuple[ZonneplanBatterySensorEntityDescription, ...] = (
    ZonneplanBatterySensorEntityDescription(
        key="state_of_charge",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda battery: battery.state_of_charge_percent,
    ),
    ZonneplanBatterySensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        # The API reports positive while charging; HA uses positive while discharging.
        value_fn=lambda battery: (
            None if battery.power_ac is None else -battery.power_ac
        ),
    ),
    ZonneplanBatterySensorEntityDescription(
        key="battery_state",
        translation_key="battery_state",
        device_class=SensorDeviceClass.ENUM,
        options=BATTERY_STATES,
        value_fn=lambda battery: _battery_state(battery.battery_state),
    ),
    ZonneplanBatterySensorEntityDescription(
        key="inverter_state",
        translation_key="inverter_state",
        device_class=SensorDeviceClass.ENUM,
        options=BATTERY_STATES,
        value_fn=lambda battery: _battery_state(battery.inverter_state),
    ),
    ZonneplanBatterySensorEntityDescription(
        key="total_earned",
        translation_key="total_earned",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda battery: battery.total_earned,
    ),
    ZonneplanBatterySensorEntityDescription(
        key="earned_today",
        translation_key="earned_today",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda battery: battery.total_day,
        last_reset_fn=lambda data: data.day_start,
    ),
    ZonneplanBatterySensorEntityDescription(
        key="energy_charged_today",
        translation_key="energy_charged_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda battery: battery.delivery_day_kwh,
    ),
    ZonneplanBatterySensorEntityDescription(
        key="energy_discharged_today",
        translation_key="energy_discharged_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda battery: battery.production_day_kwh,
    ),
    ZonneplanBatterySensorEntityDescription(
        key="cycle_count",
        translation_key="cycle_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda battery: battery.cycle_count,
    ),
    ZonneplanBatterySensorEntityDescription(
        key="backup_power_capacity",
        translation_key="backup_power_capacity",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda battery: battery.backup_power_usable_capacity_wh,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZonneplanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zonneplan sensor platform."""
    coordinator = entry.runtime_data.coordinator
    battery_coordinator = entry.runtime_data.battery_coordinator

    async_add_entities(
        [
            *(
                ZonneplanPriceSensor(coordinator, description)
                for description in ZONNEPLAN_SENSORS
            ),
            *(
                ZonneplanUsageSensor(coordinator, description)
                for description in ZONNEPLAN_USAGE_SENSORS
            ),
            *(
                ZonneplanBatterySensor(battery_coordinator, contract_uuid, description)
                for contract_uuid in battery_coordinator.data
                for description in ZONNEPLAN_BATTERY_SENSORS
            ),
        ]
    )


class ZonneplanPriceSensor(ZonneplanEntity, SensorEntity):
    """Representation of a Zonneplan electricity price sensor."""

    entity_description: ZonneplanPriceSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator)


class ZonneplanUsageSensor(ZonneplanEntity, SensorEntity):
    """Representation of a Zonneplan month-to-date usage sensor."""

    entity_description: ZonneplanUsageSensorEntityDescription

    @property
    @override
    def native_value(self) -> Decimal | None:
        """Return the month-to-date value, or None until the month has data."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def last_reset(self) -> datetime | None:
        """Return the start of the month the value covers."""
        group = self.entity_description.group_fn(self.coordinator.data)
        return None if group is None else group.start


class ZonneplanBatterySensor(ZonneplanBatteryEntity, SensorEntity):
    """Representation of a Zonneplan home battery sensor."""

    entity_description: ZonneplanBatterySensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | Decimal:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.battery)

    @property
    @override
    def last_reset(self) -> datetime | None:
        """Return when the value was last reset, for daily totals."""
        if self.entity_description.last_reset_fn is None:
            return None
        return self.entity_description.last_reset_fn(
            self.coordinator.data[self._contract_uuid]
        )
