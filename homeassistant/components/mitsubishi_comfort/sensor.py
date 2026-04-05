"""Sensor entities for Mitsubishi Comfort integration."""

from __future__ import annotations

from mitsubishi_comfort import IndoorUnit, KumoStation

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MitsubishiComfortConfigEntry
from .coordinator import MitsubishiComfortCoordinator
from .entity import MitsubishiComfortEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MitsubishiComfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mitsubishi Comfort sensor entities."""
    coordinators = entry.runtime_data
    entities = []
    for coordinator in coordinators.values():
        # Common sensors
        entities.append(MitsubishiComfortWifiSignalSensor(coordinator))
        # Indoor unit sensors
        if isinstance(coordinator.device, IndoorUnit):
            entities.append(MitsubishiComfortTemperatureSensor(coordinator))
            entities.append(MitsubishiComfortHumiditySensor(coordinator))
            entities.append(MitsubishiComfortSensorBatterySensor(coordinator))
            entities.append(MitsubishiComfortSensorSignalSensor(coordinator))
            entities.append(MitsubishiComfortUptimeSensor(coordinator))
        # KumoStation sensors
        if isinstance(coordinator.device, KumoStation):
            entities.append(MitsubishiComfortOutdoorTemperatureSensor(coordinator))
            entities.append(MitsubishiComfortUptimeSensor(coordinator))
    async_add_entities(entities)


class MitsubishiComfortSensorBase(MitsubishiComfortEntity, SensorEntity):
    """Base class for Mitsubishi Comfort sensors."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: MitsubishiComfortCoordinator, suffix: str, name: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device.serial}-{suffix}"
        self._attr_name = name


class MitsubishiComfortTemperatureSensor(MitsubishiComfortSensorBase):
    """Current temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "current-temperature", "Temperature")

    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        return self._device.status.room_temperature


class MitsubishiComfortHumiditySensor(MitsubishiComfortSensorBase):
    """Current humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "current-humidity", "Humidity")

    @property
    def native_value(self) -> float | None:
        """Return the current humidity."""
        return self._device.status.current_humidity


class MitsubishiComfortWifiSignalSensor(MitsubishiComfortSensorBase):
    """WiFi signal strength sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "wifi-signal", "Wi-Fi signal")

    @property
    def native_value(self) -> int | None:
        """Return the Wi-Fi signal strength."""
        return self._device.status.wifi_rssi


class MitsubishiComfortSensorBatterySensor(MitsubishiComfortSensorBase):
    """External sensor battery level."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "sensor-battery", "Sensor battery")

    @property
    def native_value(self) -> int | None:
        """Return the sensor battery level."""
        return self._device.status.sensor_battery


class MitsubishiComfortSensorSignalSensor(MitsubishiComfortSensorBase):
    """External sensor signal strength."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "sensor-signal", "Sensor signal")

    @property
    def native_value(self) -> int | None:
        """Return the external sensor signal strength."""
        return self._device.status.sensor_rssi


class MitsubishiComfortOutdoorTemperatureSensor(MitsubishiComfortSensorBase):
    """Outdoor temperature sensor (KumoStation only)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "outdoor-temperature", "Outdoor temperature")

    @property
    def native_value(self) -> float | None:
        """Return the outdoor temperature."""
        return self._device.status.outdoor_temperature


class MitsubishiComfortUptimeSensor(MitsubishiComfortSensorBase):
    """Device uptime sensor."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "uptime", "Uptime")

    @property
    def native_value(self) -> int | None:
        """Return the device uptime in seconds."""
        return self._device.status.uptime
