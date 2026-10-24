"""Sensors for WWS energy prices."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, override

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import WwsConfigEntry
from .const import DOMAIN, NAME
from .coordinator import WwsCoordinator

PRICE_UNIT = f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"


@dataclass(frozen=True, kw_only=True)
class WwsSensorEntityDescription(SensorEntityDescription):
    """Describes a WWS sensor entity."""

    value_fn: Callable[[WwsSensor], float | datetime | None]


SENSORS: tuple[WwsSensorEntityDescription, ...] = (
    WwsSensorEntityDescription(
        key="price_ct_kwh",
        translation_key="current_energy_price",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=3,
        value_fn=lambda entity: _price_value(entity.current_period, "price_ct_kwh"),
    ),
    WwsSensorEntityDescription(
        key="next_price_ct_kwh",
        translation_key="next_energy_price",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=3,
        value_fn=lambda entity: _price_value(entity.next_period, "price_ct_kwh"),
    ),
    WwsSensorEntityDescription(
        key="consumption_kwh",
        translation_key="yesterdays_consumption",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=lambda entity: _measurement_value(entity.latest_measurement),
    ),
    WwsSensorEntityDescription(
        key="updated_at",
        translation_key="updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda entity: entity.coordinator.last_update_success_time,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WwsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WWS sensors."""
    async_add_entities(WwsSensor(entry, description) for description in SENSORS)


class WwsSensor(CoordinatorEntity[WwsCoordinator], SensorEntity):
    """Represent the current WWS tariff period."""

    entity_description: WwsSensorEntityDescription

    def __init__(
        self, entry: WwsConfigEntry, description: WwsSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry.runtime_data)
        self.entity_description = description
        self.entity_id = f"{SENSOR_DOMAIN}.{DOMAIN}_{description.key}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    @override
    def native_value(self) -> float | datetime | None:
        """Return price or consumption data."""
        return self.entity_description.value_fn(self)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return details about the current tariff period or measurement."""
        if self.entity_description.key == "consumption_kwh":
            measurement: dict[str, Any] | None = self.latest_measurement
            if measurement is None:
                return None
            return {
                key: measurement[key]
                for key in ("start", "end", "source", "tariff_name")
                if key in measurement
            }

        period: dict[str, Any] | None = self.current_period
        attributes: dict[str, Any] = (
            {
                key: period[key]
                for key in ("start", "end", "tariff_name", "fallback", "is_smart")
                if key in period
            }
            if period is not None
            else {}
        )
        if self.entity_description.key == "price_ct_kwh":
            price_points = sorted(
                [
                    (_parse_datetime(price_period["start"]), price)
                    for price_period in self._price_periods
                    if (price := _price_value(price_period, "price_ct_kwh")) is not None
                ],
                key=lambda point: point[0],
            )
            attributes["price_periods"] = [
                {"start": start.isoformat(), "price": price}
                for start, price in price_points
            ]
        return attributes or None

    @property
    def _price_periods(self) -> list[dict[str, Any]]:
        """Return the price periods from the current payload."""
        data: Any = self.coordinator.data
        if isinstance(data, dict):
            data = data.get("prices")
        if isinstance(data, list):
            return [period for period in data if isinstance(period, dict)]
        return []

    @property
    def _measurements(self) -> list[dict[str, Any]]:
        """Return measurements from the current payload."""
        data: Any = self.coordinator.data
        if isinstance(data, dict):
            data = data.get("measurements")
        if isinstance(data, list):
            return [
                measurement for measurement in data if isinstance(measurement, dict)
            ]
        return []

    @property
    def _last_period(self) -> dict[str, Any] | None:
        """Find the last period containing the current time."""
        now = dt_util.now() - timedelta(minutes=15)
        for period in self._price_periods:
            start = _parse_datetime(period["start"])
            end = _parse_datetime(period["end"])
            if start <= now < end:
                return period
        return None

    @property
    def current_period(self) -> dict[str, Any] | None:
        """Find the period containing the current time."""
        now = dt_util.now()
        for period in self._price_periods:
            start = _parse_datetime(period["start"])
            end = _parse_datetime(period["end"])
            if start <= now < end:
                return period
        return None

    @property
    def next_period(self) -> dict[str, Any] | None:
        """Find the next period containing the current time."""
        next_after_now = dt_util.now() + timedelta(minutes=15)
        for period in self._price_periods:
            start = _parse_datetime(period["start"])
            end = _parse_datetime(period["end"])
            if start <= next_after_now < end:
                return period
        return None

    @property
    def latest_measurement(self) -> dict[str, Any] | None:
        """Return the previous completed quarter-hour measurement from yesterday."""
        if not self._measurements:
            return None

        now = dt_util.now().astimezone(dt_util.DEFAULT_TIME_ZONE)
        current_slot_start = now.replace(
            minute=(now.minute // 15) * 15,
            second=0,
            microsecond=0,
        )
        previous_day_target = current_slot_start - timedelta(days=1)
        previous_day_target_end = previous_day_target + timedelta(minutes=15)

        measurements = [
            measurement
            for measurement in self._measurements
            if (
                previous_day_target
                <= (
                    _measurement_start := _parse_datetime(
                        measurement["start"]
                    ).astimezone(dt_util.DEFAULT_TIME_ZONE)
                )
                < previous_day_target_end
            )
        ]

        if not measurements:
            return None

        return max(
            measurements,
            key=lambda measurement: _parse_datetime(measurement["start"]),
        )


def _parse_datetime(value: str | datetime) -> datetime:
    """Parse an API timestamp from string to datetime datatype.

    Return now if the timestamp is None.
    """
    dt_value: datetime | None
    if isinstance(value, datetime):
        dt_value = value
    else:
        dt_value = dt_util.parse_datetime(value)

    if dt_value is None:
        return dt_util.now()

    return dt_util.as_utc(dt_value)


def _price_value(period: dict[str, Any] | None, key: str) -> float | None:
    """Return a price in euros per kilowatt-hour."""
    value = period.get(key) if period else None
    if value is None:
        return None

    return float(value) / 100


def _measurement_value(measurement: dict[str, Any] | None) -> float | None:
    """Return the consumption measurement."""
    value = measurement.get("consumption_kwh") if measurement else None
    if value is None:
        return None

    return float(value)
