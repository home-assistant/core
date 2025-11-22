"""Sensor platform for Essent integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from essent_dynamic_pricing.models import EnergyData, Tariff

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EssentConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Essent sensors."""
    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    entities = [
        EssentCurrentPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY),
        EssentNextPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY),
        EssentAveragePriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY),
        EssentLowestPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY),
        EssentHighestPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY),
        EssentCurrentPriceSensor(coordinator, ENERGY_TYPE_GAS),
        EssentNextPriceSensor(coordinator, ENERGY_TYPE_GAS),
    ]

    async_add_entities(entities)


class EssentCurrentPriceSensor(EssentEntity, SensorEntity):
    """Current price sensor."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: EssentDataUpdateCoordinator,
        energy_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, energy_type)
        self._attr_unique_id = f"essent_{energy_type}_current_price"
        self._attr_name = f"{energy_type.capitalize()} current price"
        self._attr_translation_key = f"{energy_type}_current_price"

    @property
    def native_value(self) -> float | None:
        """Return the current price."""
        now = dt_util.now()
        if (data := self.energy_data) is None:
            return None
        tariffs = [*data.tariffs, *data.tariffs_tomorrow]

        for tariff in tariffs:
            start, end = _parse_tariff_times(tariff)
            if start and end and start <= now < end:
                return tariff.total_amount

        return None

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
        now = dt_util.now()
        if (data := self.energy_data) is None:
            return {}
        tariffs = [*data.tariffs, *data.tariffs_tomorrow]

        # Find current tariff
        current_tariff = None
        for tariff in tariffs:
            start, end = _parse_tariff_times(tariff)
            if start and end and start <= now < end:
                current_tariff = tariff
                break

        attributes: dict[str, Any] = {}

        # Current price breakdown
        if current_tariff:
            groups = {
                group["type"]: group.get("amount")
                for group in current_tariff.groups
                if "type" in group
            }
            attributes.update(
                {
                    "price_ex_vat": current_tariff.total_amount_ex,
                    "vat": current_tariff.total_amount_vat,
                    "market_price": groups.get("MARKET_PRICE"),
                    "purchasing_fee": groups.get("PURCHASING_FEE"),
                    "tax": groups.get("TAX"),
                    "start_time": _format_dt_str(current_tariff.start),
                    "end_time": _format_dt_str(current_tariff.end),
                }
            )

        return attributes


class EssentNextPriceSensor(EssentEntity, SensorEntity):
    """Next price sensor."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: EssentDataUpdateCoordinator,
        energy_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, energy_type)
        self._attr_unique_id = f"essent_{energy_type}_next_price"
        self._attr_name = f"{energy_type.capitalize()} next price"
        self._attr_translation_key = f"{energy_type}_next_price"

    @property
    def native_value(self) -> float | None:
        """Return the next price."""
        now = dt_util.now()
        if (data := self.energy_data) is None:
            return None
        tariffs = [*data.tariffs, *data.tariffs_tomorrow]

        for tariff in tariffs:
            start, _ = _parse_tariff_times(tariff)
            if start and start > now:
                return tariff.total_amount

        return None

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
        now = dt_util.now()
        if (data := self.energy_data) is None:
            return {}
        tariffs = [*data.tariffs, *data.tariffs_tomorrow]

        next_tariff = None
        for tariff in tariffs:
            start, _ = _parse_tariff_times(tariff)
            if start and start > now:
                next_tariff = tariff
                break

        if not next_tariff:
            return {}

        groups = {
            group["type"]: group.get("amount")
            for group in next_tariff.groups
            if "type" in group
        }

        return {
            "price_ex_vat": next_tariff.total_amount_ex,
            "vat": next_tariff.total_amount_vat,
            "market_price": groups.get("MARKET_PRICE"),
            "purchasing_fee": groups.get("PURCHASING_FEE"),
            "tax": groups.get("TAX"),
            "start_time": _format_dt_str(next_tariff.start),
            "end_time": _format_dt_str(next_tariff.end),
        }


class EssentAveragePriceSensor(EssentEntity, SensorEntity):
    """Average price today sensor."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: EssentDataUpdateCoordinator,
        energy_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, energy_type)
        self._attr_unique_id = f"essent_{energy_type}_average_today"
        self._attr_name = f"{energy_type.capitalize()} average today"
        self._attr_translation_key = f"{energy_type}_average_today"

    @property
    def native_value(self) -> float | None:
        """Return the average price."""
        if (data := self.energy_data) is None:
            return None
        return data.avg_price

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
        if (data := self.energy_data) is None:
            return {}
        return {
            "min_price": data.min_price,
            "max_price": data.max_price,
        }


class EssentLowestPriceSensor(EssentEntity, SensorEntity):
    """Lowest price today sensor."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None
    _attr_entity_registry_enabled_default = False
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: EssentDataUpdateCoordinator,
        energy_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, energy_type)
        self._attr_unique_id = f"essent_{energy_type}_lowest_price_today"
        self._attr_name = f"{energy_type.capitalize()} lowest price today"
        self._attr_translation_key = f"{energy_type}_lowest_price_today"

    @property
    def native_value(self) -> float | None:
        """Return the lowest price."""
        if (data := self.energy_data) is None:
            return None
        return data.min_price

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
        if (data := self.energy_data) is None:
            return {}
        tariffs = data.tariffs
        min_price = data.min_price

        # Find tariff with minimum price
        for tariff in tariffs:
            if tariff.total_amount == min_price:
                return {
                    "start": _format_dt_str(tariff.start),
                    "end": _format_dt_str(tariff.end),
                }

        return {}


class EssentHighestPriceSensor(EssentEntity, SensorEntity):
    """Highest price today sensor."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None
    _attr_entity_registry_enabled_default = False
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: EssentDataUpdateCoordinator,
        energy_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, energy_type)
        self._attr_unique_id = f"essent_{energy_type}_highest_price_today"
        self._attr_name = f"{energy_type.capitalize()} highest price today"
        self._attr_translation_key = f"{energy_type}_highest_price_today"

    @property
    def native_value(self) -> float | None:
        """Return the highest price."""
        if (data := self.energy_data) is None:
            return None
        return data.max_price

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
        if (data := self.energy_data) is None:
            return {}
        tariffs = data.tariffs
        max_price = data.max_price

        # Find tariff with maximum price
        for tariff in tariffs:
            if tariff.total_amount == max_price:
                return {
                    "start": _format_dt_str(tariff.start),
                    "end": _format_dt_str(tariff.end),
                }

        return {}
