"""Sensor platform for LoJack integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfSpeed, UnitOfElectricPotential
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_MAKE,
    ATTR_MODEL,
    ATTR_VIN,
    ATTR_YEAR,
    ATTR_LICENSE_PLATE,
    DATA_ASSETS,
    DATA_COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LoJack sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[LoJackSensor] = []

    # Create sensors for each device
    if coordinator.data and DATA_ASSETS in coordinator.data:
        for device_id, device in coordinator.data[DATA_ASSETS].items():
            # Get device name for entity naming
            device_name = _get_device_name(device)
            
            # Regular sensors
            entities.extend([
                LoJackOdometerSensor(coordinator, entry, device_id, device, device_name),
                LoJackSpeedSensor(coordinator, entry, device_id, device, device_name),
                LoJackBatteryVoltageSensor(coordinator, entry, device_id, device, device_name),
                LoJackLocationLastReportedSensor(coordinator, entry, device_id, device, device_name),
            ])
            
            # Diagnostic sensors (disabled by default)
            entities.extend([
                LoJackMakeSensor(coordinator, entry, device_id, device, device_name),
                LoJackModelSensor(coordinator, entry, device_id, device, device_name),
                LoJackYearSensor(coordinator, entry, device_id, device, device_name),
                LoJackVinSensor(coordinator, entry, device_id, device, device_name),
                LoJackLicensePlateSensor(coordinator, entry, device_id, device, device_name),
            ])

    async_add_entities(entities)


def _get_device_name(device: Any) -> str:
    """Get device name for entity naming."""
    # Get device attributes
    year = str(_get_attr(device, "year", "") or "")
    make = _get_attr(device, "make", "")
    model = _get_attr(device, "model", "")
    device_name = _get_attr(device, "name", "")
    
    # Generate device name: always use "Year Make Model" format
    if year and make and model:
        return f"{year} {make} {model}"
    elif make and model:
        return f"{make} {model}"
    elif device_name:
        return device_name
    else:
        return "Vehicle"


def _get_attr(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely get an attribute from an object."""
    if obj is None:
        return default

    # Try direct attribute access
    if hasattr(obj, attr):
        value = getattr(obj, attr, default)
        return value if value is not None else default

    # Try dictionary access
    if isinstance(obj, dict):
        return obj.get(attr, default)

    return default


def _get_location_data(device: Any) -> dict[str, Any]:
    """Extract location data from device."""
    location_data = {
        "latitude": None,
        "longitude": None,
        "accuracy": None,
        "address": None,
        "speed": None,
        "heading": None,
        "timestamp": None,
        "battery_voltage": None,
    }

    if device is None:
        return location_data

    # Try to get location from device._location (set by coordinator)
    location = _get_attr(device, "_location") or _get_attr(device, "location")

    if location:
        # Some coordinator/client implementations nest coords under `coordinates`.
        coords = _get_attr(location, "coordinates")

        if coords:
            location_data["latitude"] = _get_attr(coords, "latitude")
            location_data["longitude"] = _get_attr(coords, "longitude")
        else:
            location_data["latitude"] = _get_attr(location, "latitude")
            location_data["longitude"] = _get_attr(location, "longitude")

        # Get accuracy - may be in meters or HDOP format
        accuracy = _get_attr(location, "accuracy")
        # If accuracy is None, check for alternative field names
        if accuracy is None:
            accuracy = _get_attr(location, "gps_accuracy")
        if accuracy is None:
            # Check raw data for accuracy fields
            raw = _get_attr(location, "raw")
            if raw and isinstance(raw, dict):
                accuracy = raw.get("accuracy") or raw.get("gpsAccuracy") or raw.get("hdop")
                # If HDOP, convert to approximate meters (HDOP * 5)
                if raw.get("hdop") and accuracy == raw.get("hdop"):
                    try:
                        accuracy = float(accuracy) * 5
                    except (ValueError, TypeError):
                        pass
        location_data["accuracy"] = accuracy

        location_data["address"] = _get_attr(location, "address")
        location_data["speed"] = _get_attr(location, "speed")
        location_data["heading"] = _get_attr(location, "heading")
        location_data["timestamp"] = _get_attr(location, "timestamp")
        location_data["battery_voltage"] = _get_attr(location, "battery_voltage")

    return location_data


class LoJackSensor(CoordinatorEntity, SensorEntity):
    """Base class for LoJack sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device = device
        self._device_name = device_name
        
        # Extract vehicle info for device identification
        self._vin = _get_attr(device, "vin", "")
        self._make = _get_attr(device, "make", "")
        self._model = _get_attr(device, "model", "")

    @property
    def current_device(self) -> Any:
        """Get the current device data from coordinator."""
        if (
            self.coordinator.data
            and DATA_ASSETS in self.coordinator.data
            and self._device_id in self.coordinator.data[DATA_ASSETS]
        ):
            return self.coordinator.data[DATA_ASSETS][self._device_id]
        return self._device

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        info = {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "Spireon LoJack",
        }

        if self._make:
            info["model"] = f"{self._make} {self._model}" if self._model else self._make

        if self._vin:
            info["serial_number"] = self._vin

        return info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class LoJackOdometerSensor(LoJackSensor):
    """Sensor for vehicle odometer."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfLength.MILES
    _attr_icon = "mdi:counter"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_id, device, device_name)
        self._attr_name = "Odometer"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_odometer"

    @property
    def native_value(self) -> float | None:
        """Return the odometer value."""
        device = self.current_device
        odometer = _get_attr(device, "odometer")
        if odometer is not None:
            try:
                return round(float(odometer), 1)
            except (ValueError, TypeError):
                return None
        return None


class LoJackSpeedSensor(LoJackSensor):
    """Sensor for vehicle speed."""

    _attr_device_class = SensorDeviceClass.SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfSpeed.MILES_PER_HOUR
    _attr_icon = "mdi:speedometer"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_id, device, device_name)
        self._attr_name = "Speed"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_speed"

    @property
    def native_value(self) -> float | None:
        """Return the speed value."""
        device = self.current_device
        location = _get_location_data(device)
        
        if location.get("speed") is not None:
            try:
                return round(float(location["speed"]), 1)
            except (ValueError, TypeError):
                return None
        return None


class LoJackBatteryVoltageSensor(LoJackSensor):
    """Sensor for vehicle battery voltage."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_icon = "mdi:car-battery"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_id, device, device_name)
        self._attr_name = "Battery voltage"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_battery_voltage"

    @property
    def native_value(self) -> float | None:
        """Return the battery voltage value."""
        device = self.current_device
        # battery_voltage is part of location data in lojack-api
        location = _get_location_data(device)
        battery_voltage = location.get("battery_voltage")
        if battery_voltage is not None:
            try:
                return round(float(battery_voltage), 2)
            except (ValueError, TypeError):
                return None
        return None


class LoJackLocationLastReportedSensor(LoJackSensor):
    """Sensor for last reported location timestamp."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_id, device, device_name)
        self._attr_name = "Location last reported"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_location_last_reported"

    @property
    def native_value(self) -> datetime | None:
        """Return the last reported timestamp as a datetime object."""
        device = self.current_device
        location = _get_location_data(device)

        timestamp = location.get("timestamp")
        if timestamp:
            # Handle datetime objects directly
            if isinstance(timestamp, datetime):
                return timestamp
            # Parse ISO 8601 timestamp string
            try:
                timestamp_str = str(timestamp)
                # Handle 'Z' suffix for UTC
                if timestamp_str.endswith("Z"):
                    timestamp_str = timestamp_str[:-1] + "+00:00"
                return datetime.fromisoformat(timestamp_str)
            except (ValueError, AttributeError):
                _LOGGER.debug("Failed to parse timestamp: %s", timestamp)
                return None
        return None


class LoJackMakeSensor(LoJackSensor):
    """Diagnostic sensor for vehicle make."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:car-info"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_id, device, device_name)
        self._attr_name = "Make"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_make"
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str | None:
        """Return the make value."""
        device = self.current_device
        make = _get_attr(device, "make")
        return str(make) if make else None


class LoJackModelSensor(LoJackSensor):
    """Diagnostic sensor for vehicle model."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:car-info"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_id, device, device_name)
        self._attr_name = "Model"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_model"
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str | None:
        """Return the model value."""
        device = self.current_device
        model = _get_attr(device, "model")
        return str(model) if model else None


class LoJackYearSensor(LoJackSensor):
    """Diagnostic sensor for vehicle year."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:calendar"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_id, device, device_name)
        self._attr_name = "Year"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_year"
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str | None:
        """Return the year value."""
        device = self.current_device
        year = _get_attr(device, "year")
        return str(year) if year else None


class LoJackVinSensor(LoJackSensor):
    """Diagnostic sensor for vehicle VIN."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:identifier"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_id, device, device_name)
        self._attr_name = "VIN"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_vin"
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str | None:
        """Return the VIN value."""
        device = self.current_device
        vin = _get_attr(device, "vin")
        return str(vin) if vin else None


class LoJackLicensePlateSensor(LoJackSensor):
    """Diagnostic sensor for vehicle license plate."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:card-text"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_id, device, device_name)
        self._attr_name = "License plate"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_license_plate"
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str | None:
        """Return the license plate value."""
        device = self.current_device
        license_plate = _get_attr(device, "licensePlate") or _get_attr(device, "license_plate")
        return str(license_plate) if license_plate else None
