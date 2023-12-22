"""Support for Flo Water Monitor sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as FLO_DOMAIN
from .device import FloDeviceDataUpdateCoordinator
from .entity import FloEntity

WATER_ICON = "mdi:water"
GAUGE_ICON = "mdi:gauge"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flo sensors from config entry."""
    devices: list[FloDeviceDataUpdateCoordinator] = hass.data[FLO_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities = []
    for device in devices:
        if device.device_type == "puck_oem":
            entities.extend(
                [
                    FloTemperatureSensor(device, False),
                    FloHumiditySensor(device),
                    FloBatterySensor(device),
                ]
            )
        else:
            entities.extend(
                [
                    FloDailyUsageSensor(device),
                    FloSystemModeSensor(device),
                    FloCurrentFlowRateSensor(device),
                    FloTemperatureSensor(device, True),
                    FloPressureSensor(device),
                ]
            )
    async_add_entities(entities)


class FloDailyUsageSensor(FloEntity, SensorEntity):
    """Monitors the daily water usage."""

    _attr_icon = WATER_ICON
    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_device_class = SensorDeviceClass.WATER
    _attr_translation_key = "daily_consumption"

    def __init__(self, device):
        """Initialize the daily water usage sensor."""
        super().__init__("daily_consumption", device)

    @property
    def native_value(self) -> float | None:
        """Return the current daily usage."""
        if self._device.consumption_today is None:
            return None
        return round(self._device.consumption_today, 1)


class FloSystemModeSensor(FloEntity, SensorEntity):
    """Monitors the current Flo system mode."""

    _attr_translation_key = "current_system_mode"

    def __init__(self, device):
        """Initialize the system mode sensor."""
        super().__init__("current_system_mode", device)

    @property
    def native_value(self) -> str | None:
        """Return the current system mode."""
        if not self._device.current_system_mode:
            return None
        return self._device.current_system_mode


class FloCurrentFlowRateSensor(FloEntity, SensorEntity):
    """Monitors the current water flow rate."""

    _attr_icon = GAUGE_ICON
    _attr_native_unit_of_measurement = "gpm"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key = "current_flow_rate"

    def __init__(self, device):
        """Initialize the flow rate sensor."""
        super().__init__("current_flow_rate", device)

    @property
    def native_value(self) -> float | None:
        """Return the current flow rate."""
        if self._device.current_flow_rate is None:
            return None
        return round(self._device.current_flow_rate, 1)


class FloTemperatureSensor(FloEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device, is_water):
        """Initialize the temperature sensor."""
        super().__init__("temperature", device)
        if is_water:
            self._attr_translation_key = "water_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        if self._device.temperature is None:
            return None
        return round(self._device.temperature, 1)


class FloHumiditySensor(FloEntity, SensorEntity):
    """Monitors the humidity."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the humidity sensor."""
        super().__init__("humidity", device)

    @property
    def native_value(self) -> float | None:
        """Return the current humidity."""
        if self._device.humidity is None:
            return None
        return round(self._device.humidity, 1)


class FloPressureSensor(FloEntity, SensorEntity):
    """Monitors the water pressure."""

    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = UnitOfPressure.PSI
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key = "water_pressure"

    def __init__(self, device):
        """Initialize the pressure sensor."""
        super().__init__("water_pressure", device)

    @property
    def native_value(self) -> float | None:
        """Return the current water pressure."""
        if self._device.current_psi is None:
            return None
        return round(self._device.current_psi, 1)


class FloBatterySensor(FloEntity, SensorEntity):
    """Monitors the battery level for battery-powered leak detectors."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the battery sensor."""
        super().__init__("battery", device)

    @property
    def native_value(self) -> float | None:
        """Return the current battery level."""
        return self._device.battery_level
