"""Sensor platform for Essent integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from essent_dynamic_pricing.models import EnergyData, Tariff

from homeassistant.components.sensor import (
    EntityCategory,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import EnergyType, PriceGroup
from .coordinator import EssentConfigEntry, EssentDataUpdateCoordinator
from .entity import EssentEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class EssentSensorEntityDescription(SensorEntityDescription):
    """Describe an Essent sensor."""

    value_fn: Callable[[EnergyData], float | None]
    energy_types: tuple[EnergyType, ...] = (EnergyType.ELECTRICITY, EnergyType.GAS)


def _get_all_tariffs(data: EnergyData) -> list[Tariff]:
    """Return tariffs for both today and tomorrow."""
    return [*data.tariffs, *data.tariffs_tomorrow]


def _get_current_tariff(data: EnergyData) -> Tariff | None:
    """Return the currently active tariff."""
    now = dt_util.now()
    for tariff in _get_all_tariffs(data):
        if tariff.start is None or tariff.end is None:
            continue
        if tariff.start <= now < tariff.end:
            return tariff
    _LOGGER.debug("No current tariff found")
    return None


def _get_next_tariff(data: EnergyData) -> Tariff | None:
    """Return the next tariff."""
    now = dt_util.now()
    for tariff in _get_all_tariffs(data):
        if tariff.start is None:
            continue
        if tariff.start > now:
            return tariff
    _LOGGER.debug("No upcoming tariff found")
    return None


def _get_current_tariff_groups(
    data: EnergyData,
) -> tuple[Tariff | None, dict[str, Any]]:
    """Return the current tariff and grouped amounts."""
    if (tariff := _get_current_tariff(data)) is None:
        return None, {}
    groups = {
        group["type"]: group.get("amount") for group in tariff.groups if "type" in group
    }
    return tariff, groups


SENSORS: tuple[EssentSensorEntityDescription, ...] = (
    EssentSensorEntityDescription(
        key="current_price",
        translation_key="current_price",
        value_fn=lambda energy_data: (
            None
            if (tariff := _get_current_tariff(energy_data)) is None
            else tariff.total_amount
        ),
    ),
    EssentSensorEntityDescription(
        key="next_price",
        translation_key="next_price",
        value_fn=lambda energy_data: (
            None
            if (tariff := _get_next_tariff(energy_data)) is None
            else tariff.total_amount
        ),
        entity_registry_enabled_default=False,
    ),
    EssentSensorEntityDescription(
        key="average_today",
        translation_key="average_today",
        value_fn=lambda energy_data: energy_data.avg_price,
        energy_types=(EnergyType.ELECTRICITY,),
    ),
    EssentSensorEntityDescription(
        key="lowest_price_today",
        translation_key="lowest_price_today",
        value_fn=lambda energy_data: energy_data.min_price,
        energy_types=(EnergyType.ELECTRICITY,),
        entity_registry_enabled_default=False,
    ),
    EssentSensorEntityDescription(
        key="highest_price_today",
        translation_key="highest_price_today",
        value_fn=lambda energy_data: energy_data.max_price,
        energy_types=(EnergyType.ELECTRICITY,),
        entity_registry_enabled_default=False,
    ),
    EssentSensorEntityDescription(
        key="current_price_ex_vat",
        translation_key="current_price_ex_vat",
        value_fn=lambda energy_data: (
            None
            if (tariff := _get_current_tariff(energy_data)) is None
            else tariff.total_amount_ex
        ),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EssentSensorEntityDescription(
        key="current_price_vat",
        translation_key="current_price_vat",
        value_fn=lambda energy_data: (
            None
            if (tariff := _get_current_tariff(energy_data)) is None
            # VAT is exposed as tariff.total_amount_vat, not as a tariff group
            else tariff.total_amount_vat
        ),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EssentSensorEntityDescription(
        key="current_price_market_price",
        translation_key="current_price_market_price",
        value_fn=lambda energy_data: _get_current_tariff_groups(energy_data)[1].get(
            PriceGroup.MARKET_PRICE
        ),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EssentSensorEntityDescription(
        key="current_price_purchasing_fee",
        translation_key="current_price_purchasing_fee",
        value_fn=lambda energy_data: _get_current_tariff_groups(energy_data)[1].get(
            PriceGroup.PURCHASING_FEE
        ),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EssentSensorEntityDescription(
        key="current_price_tax",
        translation_key="current_price_tax",
        value_fn=lambda energy_data: _get_current_tariff_groups(energy_data)[1].get(
            PriceGroup.TAX
        ),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EssentConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Essent sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        EssentSensor(coordinator, energy_type, description)
        for description in SENSORS
        for energy_type in description.energy_types
    )


class EssentSensor(EssentEntity, SensorEntity):
    """Generic Essent sensor driven by entity descriptions."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    entity_description: EssentSensorEntityDescription

    def __init__(
        self,
        coordinator: EssentDataUpdateCoordinator,
        energy_type: EnergyType,
        description: EssentSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, energy_type)
        self.entity_description = description
        self._attr_unique_id = f"{energy_type}-{description.key}"
        self._attr_translation_key = f"{energy_type}_{description.translation_key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.energy_data)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return f"{CURRENCY_EURO}/{self.energy_data.unit}"
