"""Sensor platform for Essent integration."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ENERGY_TYPE_ELECTRICITY, ENERGY_TYPE_GAS
from .coordinator import EssentConfigEntry, EssentDataUpdateCoordinator
from .entity import EssentEntity

PARALLEL_UPDATES = 1


def _parse_tariff_times(tariff: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    """Parse tariff start/end times and ensure they are timezone-aware."""
    start = dt_util.parse_datetime(tariff.get("startDateTime"))
    end = dt_util.parse_datetime(tariff.get("endDateTime"))

    if start and start.tzinfo is None:
        start = dt_util.as_local(start)
    if end and end.tzinfo is None:
        end = dt_util.as_local(end)

    return start, end


def _format_dt_str(value: str | None) -> str | None:
    """Format a datetime string as local ISO, falling back to original."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    if not parsed:
        return value
    if parsed.tzinfo is None:
        parsed = dt_util.as_local(parsed)
    return parsed.isoformat()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EssentConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Essent sensors."""
    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    entities: list[SensorEntity] = []

    for energy_type in [ENERGY_TYPE_ELECTRICITY, ENERGY_TYPE_GAS]:
        entities.append(EssentCurrentPriceSensor(coordinator, energy_type))
        entities.append(EssentNextPriceSensor(coordinator, energy_type))
        if energy_type == ENERGY_TYPE_ELECTRICITY:
            entities.append(EssentAveragePriceSensor(coordinator, energy_type))
            entities.append(EssentLowestPriceSensor(coordinator, energy_type))
            entities.append(EssentHighestPriceSensor(coordinator, energy_type))

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
        data = self.coordinator.data[self.energy_type]
        tariffs: list[dict[str, Any]] = data["tariffs"] + data.get(
            "tariffs_tomorrow", []
        )

        for tariff in tariffs:
            start, end = _parse_tariff_times(tariff)
            if start and end and start <= now < end:
                return tariff.get("totalAmount")

        return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        unit = self.coordinator.data[self.energy_type]["unit"]
        return f"{CURRENCY_EURO}/{unit}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        now = dt_util.now()
        data = self.coordinator.data[self.energy_type]
        tariffs: list[dict[str, Any]] = data["tariffs"] + data.get(
            "tariffs_tomorrow", []
        )

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
                for group in current_tariff.get("groups", [])
                if "type" in group
            }
            attributes.update(
                {
                    "price_ex_vat": current_tariff.get("totalAmountEx"),
                    "vat": current_tariff.get("totalAmountVat"),
                    "market_price": groups.get("MARKET_PRICE"),
                    "purchasing_fee": groups.get("PURCHASING_FEE"),
                    "tax": groups.get("TAX"),
                    "start_time": _format_dt_str(
                        current_tariff.get("startDateTime")
                    ),
                    "end_time": _format_dt_str(current_tariff.get("endDateTime")),
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
        data = self.coordinator.data[self.energy_type]
        tariffs: list[dict[str, Any]] = data["tariffs"] + data.get(
            "tariffs_tomorrow", []
        )

        for tariff in tariffs:
            start, _ = _parse_tariff_times(tariff)
            if start and start > now:
                return tariff.get("totalAmount")

        return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        unit = self.coordinator.data[self.energy_type]["unit"]
        return f"{CURRENCY_EURO}/{unit}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        now = dt_util.now()
        data = self.coordinator.data[self.energy_type]
        tariffs: list[dict[str, Any]] = data["tariffs"] + data.get(
            "tariffs_tomorrow", []
        )

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
            for group in next_tariff.get("groups", [])
            if "type" in group
        }

        return {
            "price_ex_vat": next_tariff.get("totalAmountEx"),
            "vat": next_tariff.get("totalAmountVat"),
            "market_price": groups.get("MARKET_PRICE"),
            "purchasing_fee": groups.get("PURCHASING_FEE"),
            "tax": groups.get("TAX"),
            "start_time": _format_dt_str(next_tariff.get("startDateTime")),
            "end_time": _format_dt_str(next_tariff.get("endDateTime")),
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
        return self.coordinator.data[self.energy_type]["avg_price"]

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        unit = self.coordinator.data[self.energy_type]["unit"]
        return f"{CURRENCY_EURO}/{unit}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {
            "min_price": self.coordinator.data[self.energy_type]["min_price"],
            "max_price": self.coordinator.data[self.energy_type]["max_price"],
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
        return self.coordinator.data[self.energy_type]["min_price"]

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        unit = self.coordinator.data[self.energy_type]["unit"]
        return f"{CURRENCY_EURO}/{unit}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        tariffs = self.coordinator.data[self.energy_type]["tariffs"]
        min_price = self.coordinator.data[self.energy_type]["min_price"]

        # Find tariff with minimum price
        for tariff in tariffs:
            if tariff.get("totalAmount") == min_price:
                return {
                    "start": _format_dt_str(tariff.get("startDateTime")),
                    "end": _format_dt_str(tariff.get("endDateTime")),
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
        return self.coordinator.data[self.energy_type]["max_price"]

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        unit = self.coordinator.data[self.energy_type]["unit"]
        return f"{CURRENCY_EURO}/{unit}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        tariffs = self.coordinator.data[self.energy_type]["tariffs"]
        max_price = self.coordinator.data[self.energy_type]["max_price"]

        # Find tariff with maximum price
        for tariff in tariffs:
            if tariff.get("totalAmount") == max_price:
                return {
                    "start": _format_dt_str(tariff.get("startDateTime")),
                    "end": _format_dt_str(tariff.get("endDateTime")),
                }

        return {}
