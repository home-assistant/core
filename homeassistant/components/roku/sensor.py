"""Support for Roku sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rokuecp.models import Device as RokuDevice

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RokuConfigEntry
from .entity import RokuEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RokuSensorEntityDescription(SensorEntityDescription):
    """Describes Roku sensor entity."""

    value_fn: Callable[[RokuDevice], str | None]


SENSORS: tuple[RokuSensorEntityDescription, ...] = (
    RokuSensorEntityDescription(
        key="active_app",
        translation_key="active_app",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.app.name if device.app else None,
    ),
    RokuSensorEntityDescription(
        key="active_app_id",
        translation_key="active_app_id",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.app.app_id if device.app else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RokuConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roku sensor based on a config entry."""
    async_add_entities(
        RokuSensorEntity(
            coordinator=entry.runtime_data,
            description=description,
        )
        for description in SENSORS
    )


class RokuSensorEntity(RokuEntity, SensorEntity):
    """Defines a Roku sensor entity."""

    entity_description: RokuSensorEntityDescription

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
