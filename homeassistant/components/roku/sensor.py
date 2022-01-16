"""Support for Roku binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from rokuecp.models import Device as RokuDevice

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import RokuDataUpdateCoordinator
from .models import RokuEntity


@dataclass
class RokuSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[RokuDevice], datetime | StateType]


@dataclass
class RokuSensorEntityDescription(
    SensorEntityDescription, RokuSensorEntityDescriptionMixin
):
    """Describes Roku sensor entity."""


SENSORS: tuple[RokuSensorEntityDescription, ...] = (
    RokuSensorEntityDescription(
        key="active_app_id",
        name="Active App ID",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:application-cog",
        value_fn=lambda device: device.app.app_id,
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
        ) for description in SENSORS
    )


class RokuSensorEntity(RokuEntity, SensorEntity):
    """Defines a Roku sensor entity."""

    entity_description: RokuSensorEntityDescription

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
