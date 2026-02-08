"""Device tracker platform for LoJack integration."""

from __future__ import annotations

import contextlib
import re
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoJackConfigEntry, LoJackCoordinator, LoJackVehicleData
from .const import (
    ATTR_ADDRESS,
    ATTR_GPS_ACCURACY,
    ATTR_HEADING,
    ATTR_LAST_POLLED,
    DOMAIN,
)


def _slugify(text: str) -> str:
    """Convert text to a valid entity_id slug."""
    if not text:
        return ""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def _generate_entity_id(vehicle: LoJackVehicleData, used_ids: set[str]) -> str:
    """Generate a unique entity_id for the device."""
    # Prefer model over name
    device_name = vehicle.model or vehicle.name or ""
    name_slug = _slugify(device_name) or "vehicle"

    # Try base entity_id
    base_id = f"lojack_{name_slug}"
    if base_id not in used_ids:
        used_ids.add(base_id)
        return base_id

    # Try with last 4 of VIN
    vin = vehicle.vin or ""
    if vin and len(vin) >= 4:
        last4 = vin[-4:].lower()
        vin_id = f"{base_id}_{last4}"
        if vin_id not in used_ids:
            used_ids.add(vin_id)
            return vin_id

        # Try with numeric suffix
        suffix = 2
        while suffix <= 100:
            suffixed_id = f"{vin_id}_{suffix}"
            if suffixed_id not in used_ids:
                used_ids.add(suffixed_id)
                return suffixed_id
            suffix += 1

    # Fallback: use numeric suffix on base
    suffix = 2
    while suffix <= 100:
        suffixed_id = f"{base_id}_{suffix}"
        if suffixed_id not in used_ids:
            used_ids.add(suffixed_id)
            return suffixed_id
        suffix += 1

    # Ultimate fallback
    return f"{base_id}_{vin[-4:] if vin else 'unknown'}"


def _get_device_name(vehicle: LoJackVehicleData) -> str:
    """Get device name for entity naming."""
    if vehicle.year and vehicle.make and vehicle.model:
        return f"{vehicle.year} {vehicle.make} {vehicle.model}"
    if vehicle.make and vehicle.model:
        return f"{vehicle.make} {vehicle.model}"
    if vehicle.name:
        return vehicle.name
    return "Vehicle"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LoJack device tracker from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[LoJackDeviceTracker] = []
    used_entity_ids: set[str] = set()

    if coordinator.data:
        for vehicle in coordinator.data.values():
            entity_id_suffix = _generate_entity_id(vehicle, used_entity_ids)
            entities.append(
                LoJackDeviceTracker(
                    coordinator,
                    vehicle,
                    entity_id_suffix,
                )
            )

    async_add_entities(entities)


class LoJackDeviceTracker(CoordinatorEntity[LoJackCoordinator], TrackerEntity):
    """Representation of a LoJack device tracker."""

    _attr_has_entity_name = True
    _attr_name = None  # Main entity of the device, uses device name directly

    def __init__(
        self,
        coordinator: LoJackCoordinator,
        vehicle: LoJackVehicleData,
        entity_id_suffix: str,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._device_id = vehicle.device_id
        self._device_name = _get_device_name(vehicle)

        # Set unique ID and entity_id
        self._attr_unique_id = f"{DOMAIN}_{vehicle.device_id}"
        self.entity_id = f"device_tracker.{entity_id_suffix}"

        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.device_id)},
            name=self._device_name,
            manufacturer="Spireon LoJack",
            model=f"{vehicle.make} {vehicle.model}"
            if vehicle.make and vehicle.model
            else vehicle.make,
            serial_number=vehicle.vin,
        )

    @property
    def _vehicle(self) -> LoJackVehicleData | None:
        """Get current vehicle data from coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._device_id)
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the device."""
        if vehicle := self._vehicle:
            return vehicle.latitude
        return None

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the device."""
        if vehicle := self._vehicle:
            return vehicle.longitude
        return None

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        if vehicle := self._vehicle:
            if vehicle.accuracy is not None:
                try:
                    return int(vehicle.accuracy)
                except (ValueError, TypeError):
                    return 0
        return 0

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device (if applicable)."""
        # LoJack devices report vehicle battery voltage, not percentage
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}

        vehicle = self._vehicle
        if not vehicle:
            return attrs

        # Last polled timestamp (from vehicle's location timestamp)
        if vehicle.timestamp is not None:
            attrs[ATTR_LAST_POLLED] = vehicle.timestamp

        # GPS accuracy
        if vehicle.accuracy is not None:
            with contextlib.suppress(ValueError, TypeError):
                attrs[ATTR_GPS_ACCURACY] = int(vehicle.accuracy)

        # Address
        if vehicle.address:
            addr = vehicle.address
            if isinstance(addr, dict):
                parts: list[str] = []
                for key in ("line1", "line2", "city", "stateOrProvince", "postalCode"):
                    val = addr.get(key) or addr.get(key.lower())
                    if val:
                        parts.append(str(val))
                if parts:
                    attrs[ATTR_ADDRESS] = ", ".join(parts)
                else:
                    attrs[ATTR_ADDRESS] = str(addr)
            else:
                attrs[ATTR_ADDRESS] = str(addr)

        # Heading
        if vehicle.heading is not None:
            attrs[ATTR_HEADING] = vehicle.heading

        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
