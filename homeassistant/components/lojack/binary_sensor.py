"""Binary sensor platform for LoJack integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoJackConfigEntry
from .coordinator import LoJackCoordinator, LoJackVehicleData
from .const import DOMAIN, MOVEMENT_SPEED_THRESHOLD


def _get_device_name(vehicle: LoJackVehicleData) -> str:
    """Get device name for entity naming."""
    if vehicle.year and vehicle.make and vehicle.model:
        return f"{vehicle.year} {vehicle.make} {vehicle.model}"
    if vehicle.make and vehicle.model:
        return f"{vehicle.make} {vehicle.model}"
    if vehicle.name:
        return vehicle.name
    return "Vehicle"


def _is_active(vehicle: LoJackVehicleData) -> bool:
    """Determine if vehicle is active (has recent location data)."""
    # Consider active if we have timestamp or coordinates
    if vehicle.timestamp:
        return True
    if vehicle.latitude is not None and vehicle.longitude is not None:
        return True
    return False


def _is_moving(vehicle: LoJackVehicleData) -> bool | None:
    """Determine if vehicle is moving based on speed."""
    if vehicle.speed is None:
        return None
    return vehicle.speed > MOVEMENT_SPEED_THRESHOLD


@dataclass(frozen=True, kw_only=True)
class LoJackBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a LoJack binary sensor entity."""

    value_fn: Callable[[LoJackVehicleData], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[LoJackBinarySensorEntityDescription, ...] = (
    LoJackBinarySensorEntityDescription(
        key="active",
        translation_key="active",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_is_active,
    ),
    LoJackBinarySensorEntityDescription(
        key="moving",
        translation_key="moving",
        device_class=BinarySensorDeviceClass.MOVING,
        value_fn=_is_moving,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LoJack binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[LoJackBinarySensor] = []

    if coordinator.data:
        for vehicle in coordinator.data.values():
            device_name = _get_device_name(vehicle)
            entities.extend(
                LoJackBinarySensor(coordinator, vehicle, device_name, description)
                for description in BINARY_SENSOR_DESCRIPTIONS
            )

    async_add_entities(entities)


class LoJackBinarySensor(CoordinatorEntity[LoJackCoordinator], BinarySensorEntity):
    """Representation of a LoJack binary sensor."""

    entity_description: LoJackBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LoJackCoordinator,
        vehicle: LoJackVehicleData,
        device_name: str,
        description: LoJackBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = vehicle.device_id

        self._attr_unique_id = f"{vehicle.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.device_id)},
            name=device_name,
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
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        if vehicle := self._vehicle:
            return self.entity_description.value_fn(vehicle)
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
