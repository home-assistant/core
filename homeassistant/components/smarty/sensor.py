"""Support for Salda Smarty XP/XV Ventilation Unit Sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .coordinator import SmartyConfigEntry, SmartyCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarty Sensor Platform."""

    coordinator = entry.runtime_data
    sensors = [
        SupplyAirTemperatureSensor(coordinator),
        ExtractAirTemperatureSensor(coordinator),
        OutdoorAirTemperatureSensor(coordinator),
        SupplyFanSpeedSensor(coordinator),
        ExtractFanSpeedSensor(coordinator),
        FilterDaysLeftSensor(coordinator),
    ]

    async_add_entities(sensors)


class SmartySensor(CoordinatorEntity[SmartyCoordinator], SensorEntity):
    """Representation of a Smarty Sensor."""

    def __init__(
        self,
        coordinator: SmartyCoordinator,
        name: str,
        key: str,
        device_class: SensorDeviceClass | None,
        unit_of_measurement: str | None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.config_entry.title} {name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_native_value = None
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit_of_measurement


class SupplyAirTemperatureSensor(SmartySensor):
    """Supply Air Temperature Sensor."""

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Supply Air Temperature Init."""
        super().__init__(
            coordinator,
            name="Supply Air Temperature",
            key="supply_air_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            unit_of_measurement=UnitOfTemperature.CELSIUS,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.client.supply_air_temperature


class ExtractAirTemperatureSensor(SmartySensor):
    """Extract Air Temperature Sensor."""

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Supply Air Temperature Init."""
        super().__init__(
            coordinator,
            name="Extract Air Temperature",
            key="extract_air_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            unit_of_measurement=UnitOfTemperature.CELSIUS,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.client.extract_air_temperature


class OutdoorAirTemperatureSensor(SmartySensor):
    """Extract Air Temperature Sensor."""

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Outdoor Air Temperature Init."""
        super().__init__(
            coordinator,
            name="Outdoor Air Temperature",
            key="outdoor_air_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            unit_of_measurement=UnitOfTemperature.CELSIUS,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.client.outdoor_air_temperature


class SupplyFanSpeedSensor(SmartySensor):
    """Supply Fan Speed RPM."""

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Supply Fan Speed RPM Init."""
        super().__init__(
            coordinator,
            name="Supply Fan Speed",
            key="supply_fan_speed",
            device_class=None,
            unit_of_measurement=None,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.client.supply_fan_speed


class ExtractFanSpeedSensor(SmartySensor):
    """Extract Fan Speed RPM."""

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Extract Fan Speed RPM Init."""
        super().__init__(
            coordinator,
            name="Extract Fan Speed",
            key="extract_fan_speed",
            device_class=None,
            unit_of_measurement=None,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.client.extract_fan_speed


class FilterDaysLeftSensor(SmartySensor):
    """Filter Days Left."""

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Filter Days Left Init."""
        super().__init__(
            coordinator,
            name="Filter Days Left",
            key="filter_days_left",
            device_class=SensorDeviceClass.TIMESTAMP,
            unit_of_measurement=None,
        )
        self._days_left = 91

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        days_left = self.coordinator.client.filter_timer
        if days_left is not None and days_left != self._days_left:
            self._days_left = days_left
            return dt_util.now() + timedelta(days=days_left)
        return None
