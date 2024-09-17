"""PrusaLink binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pyprusalink.types import JobInfo, PrinterInfo, PrinterStatus
from pyprusalink.types_legacy import LegacyPrinterStatus

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PrusaLinkEntity
from .const import DOMAIN
from .coordinator import PrusaLinkUpdateCoordinator

T = TypeVar("T", PrinterStatus, LegacyPrinterStatus, JobInfo, PrinterInfo)


@dataclass(frozen=True)
class PrusaLinkBinarySensorEntityDescriptionMixin(Generic[T]):
    """Mixin for required keys."""

    value_fn: Callable[[T], bool]


@dataclass(frozen=True)
class PrusaLinkBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    PrusaLinkBinarySensorEntityDescriptionMixin[T],
    Generic[T],
):
    """Describes PrusaLink sensor entity."""

    available_fn: Callable[[T], bool] = lambda _: True


BINARY_SENSORS: dict[str, tuple[PrusaLinkBinarySensorEntityDescription, ...]] = {
    "info": (
        PrusaLinkBinarySensorEntityDescription[PrinterInfo](
            key="info.mmu",
            translation_key="mmu",
            value_fn=lambda data: data["mmu"],
            entity_registry_enabled_default=False,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PrusaLink sensor based on a config entry."""
    coordinators: dict[str, PrusaLinkUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]

    entities: list[PrusaLinkEntity] = []
    for coordinator_type, binary_sensors in BINARY_SENSORS.items():
        coordinator = coordinators[coordinator_type]
        entities.extend(
            PrusaLinkBinarySensorEntity(coordinator, sensor_description)
            for sensor_description in binary_sensors
        )

    async_add_entities(entities)


class PrusaLinkBinarySensorEntity(PrusaLinkEntity, BinarySensorEntity):
    """Defines a PrusaLink binary sensor."""

    entity_description: PrusaLinkBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PrusaLinkUpdateCoordinator,
        description: PrusaLinkBinarySensorEntityDescription,
    ) -> None:
        """Initialize a PrusaLink sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
