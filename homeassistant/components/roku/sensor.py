"""Support for Roku sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rokuecp.models import Device as RokuDevice

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RokuDataUpdateCoordinator
from .entity import RokuEntity


@dataclass
class RokuSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[RokuDevice], str | None]


@dataclass
class RokuSensorEntityDescription(
    SensorEntityDescription, RokuSensorEntityDescriptionMixin
):
    """Describes Roku sensor entity."""


SENSORS: tuple[RokuSensorEntityDescription, ...] = (
    RokuSensorEntityDescription(
        key="active_app",
        name="Active App",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:application",
        value_fn=lambda device: device.app.name if device.app else None,
    ),
    RokuSensorEntityDescription(
        key="active_app_id",
        name="Active App ID",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:application-cog",
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
    unique_id = coordinator.data.info.serial_number
    async_add_entities(
        RokuSensorEntity(
            device_id=unique_id,
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
