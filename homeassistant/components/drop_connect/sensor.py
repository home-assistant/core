"""Support for DROP sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_TYPE,
    DEV_FILTER,
    DEV_HUB,
    DEV_LEAK_DETECTOR,
    DEV_PROTECTION_VALVE,
    DEV_PUMP_CONTROLLER,
    DEV_RO_FILTER,
    DEV_SOFTENER,
    DOMAIN,
)
from .entity import DROPEntity

_LOGGER = logging.getLogger(__name__)

FLOW_ICON = "mdi:shower-head"
GAUGE_ICON = "mdi:gauge"
TDS_ICON = "mdi:water-opacity"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DROP sensors from config entry."""
    _LOGGER.debug(
        "Set up sensor for device type %s with entry_id is %s",
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.entry_id,
    )

    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    device_type: str = config_entry.data[CONF_DEVICE_TYPE]
    entities: list[SensorEntity] = []

    if device_type == DEV_HUB:
        entities.extend(
            [
                AverageWaterUsedSensor(coordinator),
                BatterySensor(coordinator),
                CurrentFlowRateSensor(coordinator),
                CurrentSystemPressureSensor(coordinator),
                HighSystemPressureSensor(coordinator),
                LowSystemPressureSensor(coordinator),
                PeakFlowRateSensor(coordinator),
                WaterUsedTodaySensor(coordinator),
            ]
        )
    elif device_type == DEV_SOFTENER:
        entities.extend(
            [
                BatterySensor(coordinator),
                CapacityRemainingSensor(coordinator),
                CurrentFlowRateSensor(coordinator),
                CurrentSystemPressureSensor(coordinator),
            ]
        )
    elif device_type == DEV_FILTER:
        entities.extend(
            [
                BatterySensor(coordinator),
                CurrentFlowRateSensor(coordinator),
                CurrentSystemPressureSensor(coordinator),
            ]
        )
    elif device_type == DEV_LEAK_DETECTOR:
        entities.extend(
            [
                BatterySensor(coordinator),
                TemperatureSensorC(coordinator),
                TemperatureSensorF(coordinator),
            ]
        )
    elif device_type == DEV_PROTECTION_VALVE:
        entities.extend(
            [
                BatterySensor(coordinator),
                CurrentFlowRateSensor(coordinator),
                CurrentSystemPressureSensor(coordinator),
                TemperatureSensorC(coordinator),
                TemperatureSensorF(coordinator),
            ]
        )
    elif device_type == DEV_PUMP_CONTROLLER:
        entities.extend(
            [
                CurrentFlowRateSensor(coordinator),
                CurrentSystemPressureSensor(coordinator),
                TemperatureSensorC(coordinator),
                TemperatureSensorF(coordinator),
            ]
        )
    elif device_type == DEV_RO_FILTER:
        entities.extend(
            [
                FilterCart1Sensor(coordinator),
                FilterCart2Sensor(coordinator),
                FilterCart3Sensor(coordinator),
                InletTdsSensor(coordinator),
                OutletTdsSensor(coordinator),
            ]
        )

    async_add_entities(entities)


class CurrentFlowRateSensor(DROPEntity, SensorEntity):
    """Monitors the current water flow rate."""

    _attr_icon = FLOW_ICON
    _attr_native_unit_of_measurement = "gpm"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key = "current_flow_rate"

    def __init__(self, device) -> None:
        """Initialize the current flow rate sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the current flow rate."""
        if self._device.current_flow_rate is None:
            return None
        return round(self._device.current_flow_rate, 1)


class PeakFlowRateSensor(DROPEntity, SensorEntity):
    """Monitors the peak water flow rate for the day."""

    _attr_icon = FLOW_ICON
    _attr_native_unit_of_measurement = "gpm"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key = "peak_flow_rate"

    def __init__(self, device) -> None:
        """Initialize the peak flow rate sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the peak flow rate."""
        if self._device.peak_flow_rate is None:
            return None
        return round(self._device.peak_flow_rate, 1)


class WaterUsedTodaySensor(DROPEntity, SensorEntity):
    """Monitors the total water used for the day."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_translation_key = "water_used_today"

    def __init__(self, device) -> None:
        """Initialize the water used today sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the total used today."""
        if self._device.water_used_today is None:
            return None
        return round(self._device.water_used_today, 1)


class AverageWaterUsedSensor(DROPEntity, SensorEntity):
    """Monitors the average water used over the last 90 days."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_translation_key = "average_water_used"

    def __init__(self, device) -> None:
        """Initialize the average water used sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the average used over the last 90 days."""
        if self._device.average_water_used is None:
            return None
        return round(self._device.average_water_used, 1)


class CapacityRemainingSensor(DROPEntity, SensorEntity):
    """Monitors the soft water capacity remaining on a softener."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_translation_key = "capacity_remaining"

    def __init__(self, device) -> None:
        """Initialize the softener capacity remaining sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the softener capacity remaining ."""
        if self._device.capacity_remaining is None:
            return None
        return round(self._device.capacity_remaining, 1)


class CurrentSystemPressureSensor(DROPEntity, SensorEntity):
    """Monitors the current system pressure."""

    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = "psi"
    _attr_translation_key = "current_system_pressure"

    def __init__(self, device) -> None:
        """Initialize the current system pressure sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the current system pressure."""
        if self._device.current_system_pressure is None:
            return None
        return round(self._device.current_system_pressure, 1)


class HighSystemPressureSensor(DROPEntity, SensorEntity):
    """Monitors the high system pressure today."""

    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = "psi"
    _attr_translation_key = "high_system_pressure"

    def __init__(self, device) -> None:
        """Initialize the high system pressure today sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the high system pressure today."""
        if self._device.high_system_pressure is None:
            return None
        return round(self._device.high_system_pressure, 1)


class LowSystemPressureSensor(DROPEntity, SensorEntity):
    """Monitors the low system pressure today."""

    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = "psi"
    _attr_translation_key = "low_system_pressure"

    def __init__(self, device) -> None:
        """Initialize the low system pressure today sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the low system pressure today."""
        if self._device.low_system_pressure is None:
            return None
        return round(self._device.low_system_pressure, 1)


class BatterySensor(DROPEntity, SensorEntity):
    """Monitors the battery level."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"
    _attr_translation_key = "battery"

    def __init__(self, device) -> None:
        """Initialize the battery sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the battery level."""
        if self._device.battery is None:
            return None
        return round(self._device.battery, 1)


class TemperatureSensorF(DROPEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°F"
    _attr_translation_key = "temperature_f"

    def __init__(self, device) -> None:
        """Initialize the temperature sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the temperature."""
        if self._device.temperature_f is None:
            return None
        return round(self._device.temperature_f, 1)


class TemperatureSensorC(DROPEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"
    _attr_translation_key = "temperature_c"

    def __init__(self, device) -> None:
        """Initialize the temperature sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the temperature."""
        if self._device.temperature_c is None:
            return None
        return round(self._device.temperature_c, 1)


class InletTdsSensor(DROPEntity, SensorEntity):
    """Monitors the inlet TDS."""

    _attr_icon = TDS_ICON
    _attr_native_unit_of_measurement = "ppm"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key = "inlet_tds"

    def __init__(self, device) -> None:
        """Initialize the inlet TDS sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the inlet TDS."""
        if self._device.inlet_tds is None:
            return None
        return round(self._device.inlet_tds, 1)


class OutletTdsSensor(DROPEntity, SensorEntity):
    """Monitors the outlet TDS."""

    _attr_icon = TDS_ICON
    _attr_native_unit_of_measurement = "ppm"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key = "outlet_tds"

    def __init__(self, device) -> None:
        """Initialize the outlet TDS sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the outlet TDS."""
        if self._device.outlet_tds is None:
            return None
        return round(self._device.outlet_tds, 1)


class FilterCart1Sensor(DROPEntity, SensorEntity):
    """Monitors the cartridge 1 life sensor."""

    _attr_icon = GAUGE_ICON
    _attr_native_unit_of_measurement = "%"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key = "cart1"

    def __init__(self, device) -> None:
        """Initialize the filter cartridge 1 life sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the filter cartridge 1 life."""
        if self._device.cart1 is None:
            return None
        return round(self._device.cart1, 1)


class FilterCart2Sensor(DROPEntity, SensorEntity):
    """Monitors the cartridge 2 life sensor."""

    _attr_icon = GAUGE_ICON
    _attr_native_unit_of_measurement = "%"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key = "cart2"

    def __init__(self, device) -> None:
        """Initialize the filter cartridge 2 life sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the filter cartridge 2 life."""
        if self._device.cart2 is None:
            return None
        return round(self._device.cart2, 1)


class FilterCart3Sensor(DROPEntity, SensorEntity):
    """Monitors the cartridge 3 life sensor."""

    _attr_icon = GAUGE_ICON
    _attr_native_unit_of_measurement = "%"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key = "cart3"

    def __init__(self, device) -> None:
        """Initialize the filter cartridge 3 life sensor."""
        super().__init__(self._attr_translation_key, device)

    @property
    def native_value(self) -> float | None:
        """Return the filter cartridge 3 life."""
        if self._device.cart3 is None:
            return None
        return round(self._device.cart3, 1)
