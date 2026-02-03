"""Device tracker platform for LoJack integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ADDRESS,
    ATTR_GPS_ACCURACY,
    ATTR_HEADING,
    DATA_ASSETS,
    DATA_COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert text to a valid entity_id slug."""
    if not text:
        return ""
    # Convert to lowercase and replace spaces/special chars with underscores
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    # Remove leading/trailing underscores
    slug = slug.strip('_')
    return slug


def _generate_entity_id(device: Any, used_ids: set[str]) -> str:
    """Generate a unique entity_id for the device.

    Format: lojack_{model}
    If taken: lojack_{model}_{last4vin}
    If still taken: lojack_{model}_{last4vin}_{n}

    Prefers 'model' attribute (e.g., "EV6") over 'name' which may contain
    extraneous info like VIN (e.g., "EV6 consumer asset KNDC44LA3N5052990").
    """
    # Get device model (preferred) or name as fallback
    device_name = ""
    if hasattr(device, "model") and device.model:
        device_name = device.model
    elif isinstance(device, dict) and device.get("model"):
        device_name = device.get("model", "")
    elif hasattr(device, "name"):
        device_name = device.name or ""
    elif isinstance(device, dict):
        device_name = device.get("name", "")

    # Get VIN for fallback
    vin = ""
    if hasattr(device, "vin"):
        vin = device.vin or ""
    elif isinstance(device, dict):
        vin = device.get("vin", "")

    # Slugify the device name
    name_slug = _slugify(device_name)
    if not name_slug:
        name_slug = "vehicle"

    # Try base entity_id: lojack_{name}
    base_id = f"lojack_{name_slug}"
    if base_id not in used_ids:
        used_ids.add(base_id)
        return base_id

    # Try with last 4 of VIN: lojack_{name}_{last4vin}
    if vin and len(vin) >= 4:
        last4 = vin[-4:].lower()
        vin_id = f"{base_id}_{last4}"
        if vin_id not in used_ids:
            used_ids.add(vin_id)
            return vin_id

        # Try with numeric suffix: lojack_{name}_{last4vin}_{n}
        suffix = 2
        while True:
            suffixed_id = f"{vin_id}_{suffix}"
            if suffixed_id not in used_ids:
                used_ids.add(suffixed_id)
                return suffixed_id
            suffix += 1
            if suffix > 100:  # Safety limit
                break

    # Fallback: use numeric suffix on base
    suffix = 2
    while True:
        suffixed_id = f"{base_id}_{suffix}"
        if suffixed_id not in used_ids:
            used_ids.add(suffixed_id)
            return suffixed_id
        suffix += 1
        if suffix > 100:  # Safety limit
            break

    # Ultimate fallback
    return f"{base_id}_{vin[-4:] if vin else 'unknown'}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LoJack device tracker from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[LoJackDeviceTracker] = []
    used_entity_ids: set[str] = set()

    # Create a device tracker for each device
    if coordinator.data and DATA_ASSETS in coordinator.data:
        for device_id, device in coordinator.data[DATA_ASSETS].items():
            # Generate unique entity_id
            entity_id_suffix = _generate_entity_id(device, used_entity_ids)

            entities.append(
                LoJackDeviceTracker(
                    coordinator,
                    entry,
                    device_id,
                    device,
                    entity_id_suffix,
                )
            )

    async_add_entities(entities)


class LoJackDeviceTracker(CoordinatorEntity, TrackerEntity):
    """Representation of a LoJack device tracker."""

    _attr_has_entity_name = True
    _attr_name = None  # Main entity of the device, uses device name directly

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        device_id: str,
        device: Any,
        entity_id_suffix: str,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device = device

        # Extract vehicle info for device identification
        self._vin = self._get_attr(device, "vin", "")
        self._make = self._get_attr(device, "make", "")
        self._model = self._get_attr(device, "model", "")
        self._year = str(self._get_attr(device, "year", "") or "")
        self._color = self._get_attr(device, "color", "")
        self._device_name = self._get_attr(device, "name", "")

        # Generate device name: always use "Year Make Model" format
        if self._year and self._make and self._model:
            self._friendly_name = f"{self._year} {self._make} {self._model}"
        elif self._make and self._model:
            self._friendly_name = f"{self._make} {self._model}"
        elif self._device_name:
            self._friendly_name = self._device_name
        else:
            self._friendly_name = f"Vehicle {device_id}"

        # Set unique ID
        self._attr_unique_id = f"{DOMAIN}_{device_id}"

        # Set entity_id to lojack_{name} format
        self.entity_id = f"device_tracker.{entity_id_suffix}"

    def _get_attr(self, obj: Any, attr: str, default: Any = None) -> Any:
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

    def _get_location_data(self, device: Any) -> dict[str, Any]:
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
        location = self._get_attr(device, "_location") or self._get_attr(device, "location")

        if location:
            # Some coordinator/client implementations nest coords under `coordinates`.
            coords = self._get_attr(location, "coordinates")

            if coords:
                location_data["latitude"] = self._get_attr(coords, "latitude")
                location_data["longitude"] = self._get_attr(coords, "longitude")
            else:
                location_data["latitude"] = self._get_attr(location, "latitude")
                location_data["longitude"] = self._get_attr(location, "longitude")

            # Get accuracy - may be in meters or HDOP format
            accuracy = self._get_attr(location, "accuracy")
            # If accuracy is None, check for alternative field names
            if accuracy is None:
                accuracy = self._get_attr(location, "gps_accuracy")
            if accuracy is None:
                # Check raw data for accuracy fields
                raw = self._get_attr(location, "raw")
                if raw and isinstance(raw, dict):
                    accuracy = raw.get("accuracy") or raw.get("gpsAccuracy") or raw.get("hdop")
                    # If HDOP, convert to approximate meters (HDOP * 5)
                    if raw.get("hdop") and accuracy == raw.get("hdop"):
                        try:
                            accuracy = float(accuracy) * 5
                        except (ValueError, TypeError):
                            pass
            location_data["accuracy"] = accuracy

            location_data["address"] = self._get_attr(location, "address")
            location_data["speed"] = self._get_attr(location, "speed")
            location_data["heading"] = self._get_attr(location, "heading")
            location_data["timestamp"] = self._get_attr(location, "timestamp")
            location_data["battery_voltage"] = self._get_attr(location, "battery_voltage")

        return location_data

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
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the device."""
        location = self._get_location_data(self.current_device)
        lat = location.get("latitude")
        if lat is not None:
            try:
                return float(lat)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the device."""
        location = self._get_location_data(self.current_device)
        lng = location.get("longitude")
        if lng is not None:
            try:
                return float(lng)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        location = self._get_location_data(self.current_device)
        accuracy = location.get("accuracy")
        if accuracy is not None:
            try:
                return int(accuracy)
            except (ValueError, TypeError):
                return 0
        return 0

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device (if applicable)."""
        # LoJack devices report vehicle battery voltage, not percentage
        return None

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        info = {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._friendly_name,
            "manufacturer": "Spireon LoJack",
        }

        if self._make:
            info["model"] = f"{self._make} {self._model}" if self._model else self._make

        if self._vin:
            info["serial_number"] = self._vin

        return info

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        device = self.current_device
        attrs: dict[str, Any] = {}

        # Location-related attributes only
        location = self._get_location_data(device)

        # GPS accuracy
        accuracy = location.get("accuracy")
        if accuracy is not None:
            try:
                attrs[ATTR_GPS_ACCURACY] = int(accuracy)
            except (ValueError, TypeError):
                pass

        # Address
        if location.get("address"):
            addr = location["address"]
            # If the address is a dict, format common parts into a readable string
            if isinstance(addr, dict):
                parts: list[str] = []
                # Common keys returned by the API
                for key in ("line1", "line2", "city", "stateOrProvince", "postalCode"):
                    # Support both camelCase and lowercase keys just in case
                    val = addr.get(key)
                    if val is None:
                        val = addr.get(key.lower())
                    if val:
                        parts.append(str(val))

                if parts:
                    attrs[ATTR_ADDRESS] = ", ".join(parts)
                else:
                    attrs[ATTR_ADDRESS] = str(addr)
            else:
                attrs[ATTR_ADDRESS] = str(addr)

        # Heading
        if location.get("heading") is not None:
            try:
                attrs[ATTR_HEADING] = float(location["heading"])
            except (ValueError, TypeError):
                pass

        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
