"""Support for RDW sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from vehicle import Vehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RDWConfigEntry, RDWDataUpdateCoordinator
from .entity import RDWEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RDWSensorEntityDescription(SensorEntityDescription):
    """Describes RDW sensor entity."""

    value_fn: Callable[[Vehicle], date | str | float | None]


SENSORS: tuple[RDWSensorEntityDescription, ...] = (
    RDWSensorEntityDescription(
        key="apk_expiration",
        translation_key="apk_expiration",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda vehicle: vehicle.apk_expiration,
    ),
    RDWSensorEntityDescription(
        key="ascription_date",
        translation_key="ascription_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda vehicle: vehicle.ascription_date,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RDWConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RDW sensors based on a config entry."""
    async_add_entities(
        RDWSensorEntity(entry.runtime_data, description) for description in SENSORS
    )


class RDWSensorEntity(RDWEntity, SensorEntity):
    """Defines an RDW sensor."""

    entity_description: RDWSensorEntityDescription

    def __init__(
        self,
        coordinator: RDWDataUpdateCoordinator,
        description: RDWSensorEntityDescription,
    ) -> None:
        """Initialize RDW sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.license_plate}_{description.key}"

    @property
    def native_value(self) -> date | str | float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
