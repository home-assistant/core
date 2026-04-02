"""Binary sensors for Ituran vehicles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyituran import Vehicle

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IturanConfigEntry
from .coordinator import IturanDataUpdateCoordinator
from .entity import IturanBaseEntity


@dataclass(frozen=True, kw_only=True)
class IturanBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Ituran binary sensor entity."""

    value_fn: Callable[[Vehicle], bool]
    supported_fn: Callable[[Vehicle], bool] = lambda _: True


BINARY_SENSOR_TYPES: list[IturanBinarySensorEntityDescription] = [
    IturanBinarySensorEntityDescription(
        key="is_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda vehicle: vehicle.is_charging,
        supported_fn=lambda vehicle: vehicle.is_electric_vehicle,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IturanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ituran binary sensors from config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        IturanBinarySensor(coordinator, vehicle.license_plate, description)
        for vehicle in coordinator.data.values()
        for description in BINARY_SENSOR_TYPES
        if description.supported_fn(vehicle)
    )


class IturanBinarySensor(IturanBaseEntity, BinarySensorEntity):
    """Ituran binary sensor."""

    entity_description: IturanBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: IturanDataUpdateCoordinator,
        license_plate: str,
        description: IturanBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, license_plate, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.vehicle)
