"""Support for RDW binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vehicle import Vehicle

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


@dataclass
class RDWBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[Vehicle], bool | None]


@dataclass
class RDWBinarySensorEntityDescription(
    BinarySensorEntityDescription, RDWBinarySensorEntityDescriptionMixin
):
    """Describes RDW binary sensor entity."""


BINARY_SENSORS: tuple[RDWBinarySensorEntityDescription, ...] = (
    RDWBinarySensorEntityDescription(
        key="liability_insured",
        translation_key="liability_insured",
        icon="mdi:shield-car",
        is_on_fn=lambda vehicle: vehicle.liability_insured,
    ),
    RDWBinarySensorEntityDescription(
        key="pending_recall",
        translation_key="pending_recall",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda vehicle: vehicle.pending_recall,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RDW binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RDWBinarySensorEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in BINARY_SENSORS
        if description.is_on_fn(coordinator.data) is not None
    )


class RDWBinarySensorEntity(
    CoordinatorEntity[DataUpdateCoordinator[Vehicle]], BinarySensorEntity
):
    """Defines an RDW binary sensor."""

    entity_description: RDWBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: DataUpdateCoordinator[Vehicle],
        description: RDWBinarySensorEntityDescription,
    ) -> None:
        """Initialize RDW binary sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.license_plate}_{description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.data.license_plate)},
            manufacturer=coordinator.data.brand,
            name=f"{coordinator.data.brand} {coordinator.data.license_plate}",
            model=coordinator.data.model,
            configuration_url=f"https://ovi.rdw.nl/default.aspx?kenteken={coordinator.data.license_plate}",
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return bool(self.entity_description.is_on_fn(self.coordinator.data))
