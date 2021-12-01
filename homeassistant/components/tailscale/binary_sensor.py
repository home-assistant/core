"""Support for Tailscale binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tailscale import Device as TailscaleDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TailscaleEntity
from .const import DOMAIN


@dataclass
class TailscaleBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[TailscaleDevice], bool | None]


@dataclass
class TailscaleBinarySensorEntityDescription(
    BinarySensorEntityDescription, TailscaleBinarySensorEntityDescriptionMixin
):
    """Describes a Tailscale binary sensor entity."""


BINARY_SENSORS: tuple[TailscaleBinarySensorEntityDescription, ...] = (
    TailscaleBinarySensorEntityDescription(
        key="update_available",
        name="Client",
        device_class=BinarySensorDeviceClass.UPDATE,
        is_on_fn=lambda device: device.update_available,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Tailscale binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TailscaleBinarySensorEntity(
            coordinator=coordinator,
            device=device,
            description=description,
        )
        for device in coordinator.data.values()
        for description in BINARY_SENSORS
    )


class TailscaleBinarySensorEntity(TailscaleEntity, BinarySensorEntity):
    """Defines a Tailscale binary sensor."""

    entity_description: TailscaleBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return bool(
            self.entity_description.is_on_fn(self.coordinator.data[self.device_id])
        )
