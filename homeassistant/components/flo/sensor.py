"""Support for Flo Water Monitor sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_PSI,
    TEMP_FAHRENHEIT,
    VOLUME_GALLONS,
)

from .const import DOMAIN as FLO_DOMAIN
from .device import FloDeviceDataUpdateCoordinator
from .entity import FloEntity

WATER_ICON = "mdi:water"
GAUGE_ICON = "mdi:gauge"
NAME_DAILY_USAGE = "Today's Water Usage"
NAME_CURRENT_SYSTEM_MODE = "Current System Mode"
NAME_FLOW_RATE = "Water Flow Rate"
NAME_WATER_TEMPERATURE = "Water Temperature"
NAME_AIR_TEMPERATURE = "Temperature"
NAME_WATER_PRESSURE = "Water Pressure"
NAME_HUMIDITY = "Humidity"
NAME_BATTERY = "Battery"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flo sensors from config entry."""
    devices: list[FloDeviceDataUpdateCoordinator] = hass.data[FLO_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities = []
    for device in devices:
        if device.device_type == "puck_oem":
            entities.extend(
                [
                    FloTemperatureSensor(NAME_AIR_TEMPERATURE, device),
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
                    FloTemperatureSensor(NAME_WATER_TEMPERATURE, device),
                    FloPressureSensor(device),
                ]
            )
    async_add_entities(entities)


class FloDailyUsageSensor(FloEntity, SensorEntity):
    """Monitors the daily water usage."""

    def __init__(self, device):
        """Initialize the daily water usage sensor."""
        super().__init__("daily_consumption", NAME_DAILY_USAGE, device)
        self._state: float = None

    @property
    def icon(self) -> str:
        """Return the daily usage icon."""
        return WATER_ICON

    @property
    def state(self) -> float | None:
        """Return the current daily usage."""
        if self._device.consumption_today is None:
            return None
        return round(self._device.consumption_today, 1)

    @property
    def unit_of_measurement(self) -> str:
        """Return gallons as the unit measurement for water."""
        return VOLUME_GALLONS


class FloSystemModeSensor(FloEntity, SensorEntity):
    """Monitors the current Flo system mode."""

    def __init__(self, device):
        """Initialize the system mode sensor."""
        super().__init__("current_system_mode", NAME_CURRENT_SYSTEM_MODE, device)
        self._state: str = None

    @property
    def state(self) -> str | None:
        """Return the current system mode."""
        if not self._device.current_system_mode:
            return None
        return self._device.current_system_mode


class FloCurrentFlowRateSensor(FloEntity, SensorEntity):
    """Monitors the current water flow rate."""

    def __init__(self, device):
        """Initialize the flow rate sensor."""
        super().__init__("current_flow_rate", NAME_FLOW_RATE, device)
        self._state: float = None

    @property
    def icon(self) -> str:
        """Return the daily usage icon."""
        return GAUGE_ICON

    @property
    def state(self) -> float | None:
        """Return the current flow rate."""
        if self._device.current_flow_rate is None:
            return None
        return round(self._device.current_flow_rate, 1)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit measurement."""
        return "gpm"


class FloTemperatureSensor(FloEntity, SensorEntity):
    """Monitors the temperature."""

    def __init__(self, name, device):
        """Initialize the temperature sensor."""
        super().__init__("temperature", name, device)
        self._state: float = None

    @property
    def state(self) -> float | None:
        """Return the current temperature."""
        if self._device.temperature is None:
            return None
        return round(self._device.temperature, 1)

    @property
    def unit_of_measurement(self) -> str:
        """Return fahrenheit as the unit measurement for temperature."""
        return TEMP_FAHRENHEIT

    @property
    def device_class(self) -> str | None:
        """Return the device class for this sensor."""
        return DEVICE_CLASS_TEMPERATURE


class FloHumiditySensor(FloEntity, SensorEntity):
    """Monitors the humidity."""

    def __init__(self, device):
        """Initialize the humidity sensor."""
        super().__init__("humidity", NAME_HUMIDITY, device)
        self._state: float = None

    @property
    def state(self) -> float | None:
        """Return the current humidity."""
        if self._device.humidity is None:
            return None
        return round(self._device.humidity, 1)

    @property
    def unit_of_measurement(self) -> str:
        """Return percent as the unit measurement for humidity."""
        return PERCENTAGE

    @property
    def device_class(self) -> str | None:
        """Return the device class for this sensor."""
        return DEVICE_CLASS_HUMIDITY


class FloPressureSensor(FloEntity, SensorEntity):
    """Monitors the water pressure."""

    def __init__(self, device):
        """Initialize the pressure sensor."""
        super().__init__("water_pressure", NAME_WATER_PRESSURE, device)
        self._state: float = None

    @property
    def state(self) -> float | None:
        """Return the current water pressure."""
        if self._device.current_psi is None:
            return None
        return round(self._device.current_psi, 1)

    @property
    def unit_of_measurement(self) -> str:
        """Return gallons as the unit measurement for water."""
        return PRESSURE_PSI

    @property
    def device_class(self) -> str | None:
        """Return the device class for this sensor."""
        return DEVICE_CLASS_PRESSURE


class FloBatterySensor(FloEntity, SensorEntity):
    """Monitors the battery level for battery-powered leak detectors."""

    def __init__(self, device):
        """Initialize the battery sensor."""
        super().__init__("battery", NAME_BATTERY, device)
        self._state: float = None

    @property
    def state(self) -> float | None:
        """Return the current battery level."""
        return self._device.battery_level

    @property
    def unit_of_measurement(self) -> str:
        """Return percentage as the unit measurement for battery."""
        return PERCENTAGE

    @property
    def device_class(self) -> str | None:
        """Return the device class for this sensor."""
        return DEVICE_CLASS_BATTERY
