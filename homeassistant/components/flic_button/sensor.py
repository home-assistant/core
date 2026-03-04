"""Sensor platform for Flic Button integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlicButtonConfigEntry
from .const import DeviceType
from .coordinator import FlicCoordinator
from .entity import FlicButtonEntity

PARALLEL_UPDATES = 0

# Piecewise linear discharge curves: (voltage, percentage) pairs sorted by voltage.
# CR2032 coin cell (Flic 2) and rechargeable (Duo) — from firmware formula.
_DISCHARGE_CURVE_COIN_CELL: tuple[tuple[float, int], ...] = (
    (2.1, 0),
    (2.44, 6),
    (2.74, 18),
    (2.9, 42),
    (3.0, 100),
)

# 2x AAA alkaline (Flic Twist) operates in a 1.8-3.2V range.
_DISCHARGE_CURVE_AAA: tuple[tuple[float, int], ...] = (
    (1.8, 0),
    (2.0, 5),
    (2.4, 10),
    (2.6, 25),
    (2.8, 50),
    (3.0, 80),
    (3.2, 100),
)


def _voltage_to_percentage(voltage: float, curve: tuple[tuple[float, int], ...]) -> int:
    """Convert voltage to percentage using piecewise linear interpolation."""
    if voltage <= curve[0][0]:
        return curve[0][1]
    if voltage >= curve[-1][0]:
        return curve[-1][1]

    for i in range(1, len(curve)):
        v_low, p_low = curve[i - 1]
        v_high, p_high = curve[i]
        if voltage <= v_high:
            fraction = (voltage - v_low) / (v_high - v_low)
            return int(p_low + fraction * (p_high - p_low))

    return curve[-1][1]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlicButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flic Button sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities([FlicBatterySensor(coordinator)])


class FlicBatterySensor(FlicButtonEntity, SensorEntity):
    """Battery level sensor for Flic button."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "battery"

    def __init__(self, coordinator: FlicCoordinator) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.address}-battery"

    @property
    def native_value(self) -> int | None:
        """Return battery level percentage."""
        if self.coordinator.data is None:
            return None

        voltage = self.coordinator.data.get("battery_voltage")
        if voltage is None:
            return None

        curve = (
            _DISCHARGE_CURVE_AAA
            if self.coordinator.device_type == DeviceType.TWIST
            else _DISCHARGE_CURVE_COIN_CELL
        )
        return _voltage_to_percentage(voltage, curve)
