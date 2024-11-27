"""Binary sensor platform for SABnzbd."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SabnzbdConfigEntry
from .entity import SabnzbdEntity


@dataclass(frozen=True, kw_only=True)
class SabnzbdBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Sabnzbd binary sensor entity."""

    is_on_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[SabnzbdBinarySensorEntityDescription, ...] = (
    SabnzbdBinarySensorEntityDescription(
        key="warnings",
        translation_key="warnings",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data["have_warnings"] != "0",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SabnzbdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Sabnzbd sensor entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        [SabnzbdBinarySensor(coordinator, sensor) for sensor in BINARY_SENSORS]
    )


class SabnzbdBinarySensor(SabnzbdEntity, BinarySensorEntity):
    """Representation of an SABnzbd binary sensor."""

    entity_description: SabnzbdBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return latest sensor data."""
        return self.entity_description.is_on_fn(self.coordinator.data)
