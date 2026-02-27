"""Device tracker platform for LoJack integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoJackConfigEntry
from .coordinator import LoJackCoordinator, LoJackVehicleData, get_device_name
from .const import (
    ATTR_ADDRESS,
    ATTR_HEADING,
    ATTR_LAST_POLLED,
    DOMAIN,
    LOGGER,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LoJack device tracker from a config entry."""
    coordinator = entry.runtime_data

    entities: list[LoJackDeviceTracker] = []

    if coordinator.data:
        entities.extend(
            LoJackDeviceTracker(coordinator, vehicle)
            for vehicle in coordinator.data.values()
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
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._device_id = vehicle.device_id
        self._device_name = get_device_name(vehicle)

        self._attr_unique_id = vehicle.device_id
        self._unavailable_logged = False

        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.device_id)},
            name=self._device_name,
            manufacturer="Spireon LoJack",
            model=vehicle.model if vehicle.model else None,
            serial_number=vehicle.vin,
        )

    @property
    def _vehicle(self) -> LoJackVehicleData | None:
        """Get current vehicle data from coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._device_id)
        return None

    @property
    def available(self) -> bool:
        """Return True if vehicle is still included in the account."""
        return super().available and self._vehicle is not None

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
        # Log when vehicle becomes unavailable or recovers
        coordinator_available = super().available
        vehicle_present = self._vehicle is not None
        is_available = coordinator_available and vehicle_present
        if not is_available and not self._unavailable_logged:
            if coordinator_available and not vehicle_present:
                LOGGER.info(
                    "The %s is unavailable: vehicle removed from account",
                    self._device_name,
                )
            else:
                LOGGER.info("The %s is unavailable", self._device_name)
            self._unavailable_logged = True
        elif is_available and self._unavailable_logged:
            LOGGER.info("The %s is back online", self._device_name)
            self._unavailable_logged = False

        self.async_write_ha_state()
