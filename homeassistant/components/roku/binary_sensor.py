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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import RokuEntity


@dataclass
class RokuBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[RokuDevice], bool | None]


@dataclass
class RokuBinarySensorEntityDescription(
    BinarySensorEntityDescription, RokuBinarySensorEntityDescriptionMixin
):
    """Describes a Roku binary sensor entity."""


BINARY_SENSORS: tuple[RokuBinarySensorEntityDescription, ...] = (
    RokuBinarySensorEntityDescription(
        key="headphones_connected",
        translation_key="headphones_connected",
        icon="mdi:headphones",
        value_fn=lambda device: device.info.headphones_connected,
    ),
    RokuBinarySensorEntityDescription(
        key="supports_airplay",
        translation_key="supports_airplay",
        icon="mdi:cast-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.supports_airplay,
    ),
    RokuBinarySensorEntityDescription(
        key="supports_ethernet",
        translation_key="supports_ethernet",
        icon="mdi:ethernet",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.ethernet_support,
    ),
    RokuBinarySensorEntityDescription(
        key="supports_find_remote",
        translation_key="supports_find_remote",
        icon="mdi:remote",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.supports_find_remote,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Roku binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        RokuBinarySensorEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in BINARY_SENSORS
    )


class RokuBinarySensorEntity(RokuEntity, BinarySensorEntity):
    """Defines a Roku binary sensor."""

    entity_description: RokuBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
