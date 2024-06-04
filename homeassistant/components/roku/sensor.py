"""Support for Roku sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rokuecp.models import Device as RokuDevice

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RokuDataUpdateCoordinator
from .entity import RokuEntity


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
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roku sensor based on a config entry."""
    coordinator: RokuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        RokuSensorEntity(
            coordinator=coordinator,
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
