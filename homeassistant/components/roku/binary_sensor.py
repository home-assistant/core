"""Support for Roku binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rokuecp.models import Device as RokuDevice

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import RokuEntity


@dataclass
class RokuBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[RokuDevice], bool | None]


@dataclass
class RokuBinarySensorEntityDescription(
    BinarySensorEntityDescription, RokuBinarySensorEntityDescriptionMixin
):
    """Describes a Roku binary sensor entity."""


BINARY_SENSORS: tuple[RokuBinarySensorEntityDescription, ...] = (
    RokuBinarySensorEntityDescription(
        key="supports_airplay",
        name="Supports AirPlay",
        icon="mdi:wan",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.info.supports_airplay,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Roku binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unique_id = coordinator.data.info.serial_number
    async_add_entities(
        RokuBinarySensorEntity(
            device_id=unique_id,
            coordinator=coordinator,
            description=description,
        )
        for description in BINARY_SENSORS
    )


class RokuBinarySensorEntity(RokuEntity, BinarySensorEntity):
    """Defines a Roku binary sensor."""

    entity_description: RokuBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return bool(self.entity_description.is_on_fn(self.coordinator.data))
