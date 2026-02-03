"""Binary sensor platform for LoJack integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_ASSETS,
    DATA_COORDINATOR,
    DOMAIN,
    MOVEMENT_SPEED_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LoJack binary sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[LoJackBinarySensor] = []

    # Create binary sensors for each device
    if coordinator.data and DATA_ASSETS in coordinator.data:
        for device_id, device in coordinator.data[DATA_ASSETS].items():
            # Get device name for entity naming
            device_name = _get_device_name(device)
            
            # Binary sensors
            entities.extend([
                LoJackActiveSensor(coordinator, entry, device_id, device, device_name),
                LoJackMovingSensor(coordinator, entry, device_id, device, device_name),
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

        location_data["accuracy"] = _get_attr(location, "accuracy")
        location_data["address"] = _get_attr(location, "address")
        location_data["speed"] = _get_attr(location, "speed")
        location_data["heading"] = _get_attr(location, "heading")
        location_data["timestamp"] = _get_attr(location, "timestamp")

    return location_data


class LoJackBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for LoJack binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        device_name: str,
    ) -> None:
        """Initialize the binary sensor."""
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


class LoJackActiveSensor(LoJackBinarySensor):
    """Binary sensor for vehicle connectivity status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:wifi"

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
        self._attr_name = "Active"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_active"

    @property
    def is_on(self) -> bool | None:
        """Return True if the vehicle is active/connected."""
        device = self.current_device
        location = _get_location_data(device)
        
        # Consider the vehicle active if it has recent location data
        # If timestamp exists, we assume the device is active
        if location.get("timestamp"):
            return True
        
        # If we have coordinates, consider it active
        if location.get("latitude") is not None and location.get("longitude") is not None:
            return True
        
        # Otherwise, consider it inactive
        return False


class LoJackMovingSensor(LoJackBinarySensor):
    """Binary sensor for vehicle moving status."""

    _attr_device_class = BinarySensorDeviceClass.MOVING
    _attr_icon = "mdi:car"

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
        self._attr_name = "Moving"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_moving"

    @property
    def is_on(self) -> bool | None:
        """Return True if the vehicle is moving."""
        device = self.current_device
        location = _get_location_data(device)
        
        # Check if speed is greater than the movement threshold
        speed = location.get("speed")
        if speed is not None:
            try:
                speed_val = float(speed)
                # Consider moving if speed exceeds the threshold
                # Using a small threshold to account for GPS/speed sensor inaccuracy
                return speed_val > MOVEMENT_SPEED_THRESHOLD
            except (ValueError, TypeError):
                return None
        
        return None
