"""Sensor platform for Essent integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from essent_dynamic_pricing.models import Tariff

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ENERGY_TYPE_ELECTRICITY, ENERGY_TYPE_GAS
from .coordinator import EssentConfigEntry, EssentDataUpdateCoordinator
from .entity import EssentEntity

PARALLEL_UPDATES = 1
ESSENT_TIME_ZONE = dt_util.get_time_zone("Europe/Amsterdam") or dt_util.UTC


def _parse_tariff_datetime(value: str | None) -> datetime | None:
    """Parse a tariff timestamp in the Essent time zone."""
    if not isinstance(value, str):
        return None
    parsed = dt_util.parse_datetime(value)
    if not parsed:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ESSENT_TIME_ZONE)
    return parsed.astimezone(ESSENT_TIME_ZONE)


def _parse_tariff_times(
    tariff: Tariff,
) -> tuple[datetime | None, datetime | None]:
    """Parse tariff start/end times and ensure they are timezone-aware."""
    return (
        _parse_tariff_datetime(tariff.start),
        _parse_tariff_datetime(tariff.end),
    )


def _format_dt_str(value: str | None) -> str | None:
    """Format a datetime string in the Essent time zone, falling back to original."""
    if not value:
        return None
    if parsed := _parse_tariff_datetime(value):
        return parsed.isoformat()
    return value


@dataclass(frozen=True, kw_only=True)
class EssentSensorEntityDescription(SensorEntityDescription):
    """Describe an Essent sensor."""

    value_fn: Callable[["EssentSensor"], float | None]
    attrs_fn: Callable[["EssentSensor"], dict[str, Any]] | None = None
    energy_types: tuple[str, ...] = (ENERGY_TYPE_ELECTRICITY, ENERGY_TYPE_GAS)
    entity_registry_enabled_default: bool = True


def _get_all_tariffs(entity: "EssentSensor") -> list[Tariff]:
    """Return tariffs for both today and tomorrow."""
    if (data := entity.energy_data) is None:
        return []
    return [*data.tariffs, *data.tariffs_tomorrow]


def _get_current_tariff(entity: "EssentSensor") -> Tariff | None:
    """Return the currently active tariff."""
    now = dt_util.now()
    for tariff in _get_all_tariffs(entity):
        start, end = _parse_tariff_times(tariff)
        if start and end and start <= now < end:
            return tariff
    return None


def _get_next_tariff(entity: "EssentSensor") -> Tariff | None:
    """Return the next tariff."""
    now = dt_util.now()
    for tariff in _get_all_tariffs(entity):
        start, _ = _parse_tariff_times(tariff)
        if start and start > now:
            return tariff
    return None


def _current_price_attrs(entity: "EssentSensor") -> dict[str, Any]:
    """Build attributes for the current price."""
    if (tariff := _get_current_tariff(entity)) is None:
        return {}
    groups = {
        group["type"]: group.get("amount") for group in tariff.groups if "type" in group
    }
    return {
        "price_ex_vat": tariff.total_amount_ex,
        "vat": tariff.total_amount_vat,
        "market_price": groups.get("MARKET_PRICE"),
        "purchasing_fee": groups.get("PURCHASING_FEE"),
        "tax": groups.get("TAX"),
        "start_time": _format_dt_str(tariff.start),
        "end_time": _format_dt_str(tariff.end),
    }


def _next_price_attrs(entity: "EssentSensor") -> dict[str, Any]:
    """Build attributes for the next price."""
    if (tariff := _get_next_tariff(entity)) is None:
        return {}
    groups = {
        group["type"]: group.get("amount") for group in tariff.groups if "type" in group
    }
    return {
        "price_ex_vat": tariff.total_amount_ex,
        "vat": tariff.total_amount_vat,
        "market_price": groups.get("MARKET_PRICE"),
        "purchasing_fee": groups.get("PURCHASING_FEE"),
        "tax": groups.get("TAX"),
        "start_time": _format_dt_str(tariff.start),
        "end_time": _format_dt_str(tariff.end),
    }


def _average_attrs(entity: "EssentSensor") -> dict[str, Any]:
    """Build attributes for the average price."""
    if (data := entity.energy_data) is None:
        return {}
    return {
        "min_price": data.min_price,
        "max_price": data.max_price,
    }


def _extreme_attrs(entity: "EssentSensor", target: float) -> dict[str, Any]:
    """Build attributes for lowest/highest prices."""
    if (data := entity.energy_data) is None:
        return {}
    for tariff in data.tariffs:
        if tariff.total_amount == target:
            return {
                "start": _format_dt_str(tariff.start),
                "end": _format_dt_str(tariff.end),
            }
    return {}


SENSORS: tuple[EssentSensorEntityDescription, ...] = (
    EssentSensorEntityDescription(
        key="current_price",
        name="current price",
        translation_key="current_price",
        value_fn=lambda entity: (
            None
            if (tariff := _get_current_tariff(entity)) is None
            else tariff.total_amount
        ),
        attrs_fn=_current_price_attrs,
    ),
    EssentSensorEntityDescription(
        key="next_price",
        name="next price",
        translation_key="next_price",
        value_fn=lambda entity: (
            None
            if (tariff := _get_next_tariff(entity)) is None
            else tariff.total_amount
        ),
        attrs_fn=_next_price_attrs,
    ),
    EssentSensorEntityDescription(
        key="average_today",
        name="average today",
        translation_key="average_today",
        value_fn=lambda entity: None
        if (data := entity.energy_data) is None
        else data.avg_price,
        attrs_fn=_average_attrs,
    ),
    EssentSensorEntityDescription(
        key="lowest_price_today",
        name="lowest price today",
        translation_key="lowest_price_today",
        value_fn=lambda entity: None
        if (data := entity.energy_data) is None
        else data.min_price,
        attrs_fn=lambda entity: (
            {}
            if (data := entity.energy_data) is None
            else _extreme_attrs(entity, data.min_price)
        ),
        energy_types=(ENERGY_TYPE_ELECTRICITY,),
        entity_registry_enabled_default=False,
    ),
    EssentSensorEntityDescription(
        key="highest_price_today",
        name="highest price today",
        translation_key="highest_price_today",
        value_fn=lambda entity: None
        if (data := entity.energy_data) is None
        else data.max_price,
        attrs_fn=lambda entity: (
            {}
            if (data := entity.energy_data) is None
            else _extreme_attrs(entity, data.max_price)
        ),
        energy_types=(ENERGY_TYPE_ELECTRICITY,),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EssentConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Essent sensors."""
    coordinator: EssentDataUpdateCoordinator = entry.runtime_data
    entities: list[EssentSensor] = []

    for description in SENSORS:
        for energy_type in description.energy_types:
            entities.append(EssentSensor(coordinator, energy_type, description))

    async_add_entities(entities)


class EssentSensor(EssentEntity, SensorEntity):
    """Generic Essent sensor driven by entity descriptions."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None
    _attr_suggested_display_precision = 3

    entity_description: EssentSensorEntityDescription

    def __init__(
        self,
        coordinator: EssentDataUpdateCoordinator,
        energy_type: str,
        description: EssentSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, energy_type)
        self.entity_description = description
        self._attr_unique_id = f"essent_{energy_type}_{description.key}"
        self._attr_name = f"{energy_type.capitalize()} {description.name}"
        self._attr_translation_key = f"{energy_type}_{description.translation_key}"
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        if (data := self.energy_data) is None:
            return f"{CURRENCY_EURO}/kWh"
        unit = data.unit
        return f"{CURRENCY_EURO}/{unit}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        if self.entity_description.attrs_fn is None:
            return {}
        return self.entity_description.attrs_fn(self)
