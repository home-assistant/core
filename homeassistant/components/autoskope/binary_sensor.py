"""Support for Autoskope binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from autoskope_client.constants import MANUFACTURER
from autoskope_client.models import Vehicle
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AutoskopeConfigEntry, AutoskopeDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class AutoskopeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Autoskope binary sensor entity."""

    value_fn: Callable[[Vehicle], bool | None] = lambda x: None


BINARY_SENSOR_DESCRIPTIONS: tuple[AutoskopeBinarySensorEntityDescription, ...] = (
    AutoskopeBinarySensorEntityDescription(
        key="park_mode",
        translation_key="park_mode",
        # Using MOTION device class (inverted logic: motion detected = not parked)
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda vehicle: (
            # Invert: binary sensor is ON when NOT in park mode (= motion detected)
            not vehicle.position.park_mode if vehicle.position else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutoskopeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Autoskope binary sensor entities."""
    coordinator = entry.runtime_data
    tracked_vehicles: set[str] = set()

    def update_entities() -> None:
        """Update entities based on coordinator data."""
        if not coordinator.data:
            return

        new_entities: list[AutoskopeBinarySensor] = []
        current_vehicles = set(coordinator.data.keys())

        for vehicle_id in current_vehicles - tracked_vehicles:
            if vehicle_id in coordinator.data:
                new_entities.extend(
                    AutoskopeBinarySensor(coordinator, vehicle_id, description)
                    for description in BINARY_SENSOR_DESCRIPTIONS
                )
                tracked_vehicles.add(vehicle_id)

        if new_entities:
            async_add_entities(new_entities)

    # Register listener and update immediately
    entry.async_on_unload(coordinator.async_add_listener(update_entities))
    update_entities()


class AutoskopeBinarySensor(
    CoordinatorEntity[AutoskopeDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of an Autoskope binary sensor."""

    entity_description: AutoskopeBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AutoskopeDataUpdateCoordinator,
        vehicle_id: str,
        description: AutoskopeBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"{vehicle_id}_{description.key}"

        # Set device info in constructor
        vehicle_data = coordinator.data.get(vehicle_id) if coordinator.data else None
        if vehicle_data:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(vehicle_data.id))},
                name=vehicle_data.name,
                manufacturer=MANUFACTURER,
                model=vehicle_data.model,
                serial_number=vehicle_data.imei,
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._vehicle_id in self.coordinator.data
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data or self._vehicle_id not in self.coordinator.data:
            return None

        vehicle = self.coordinator.data[self._vehicle_id]
        return self.entity_description.value_fn(vehicle)
