"""Support for interface with a Gree climate systems."""

from __future__ import annotations

import logging

from collections.abc import Callable
from dataclasses import dataclass

from greeclimate.device import Device

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATORS, DISPATCH_DEVICE_DISCOVERED, DOMAIN
from .entity import GreeEntity

_LOGGER = logging.getLogger(__name__)

@dataclass(kw_only=True, frozen=True)
class GreeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Gree binary sensor entity."""

    get_value_fn: Callable[[Device], bool]

GREE_BINARY_SENSORS: tuple[GreeBinarySensorEntityDescription, ...] = (
    GreeBinarySensorEntityDescription(
        key="Water Tank Full",
        translation_key="water_full",
        get_value_fn=lambda d: d.water_full,
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Gree HVAC device from a config entry."""

    @callback
    def init_device(coordinator):
        """Register the device."""
        
        async_add_entities(
            GreeBinarySensor(coordinator=coordinator, description=description)
            for description in GREE_BINARY_SENSORS
        )

    for coordinator in hass.data[DOMAIN][COORDINATORS]:
        init_device(coordinator)

    entry.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)
    )


class GreeBinarySensor(GreeEntity, BinarySensorEntity):
    """Generic Gree binary sensor entity."""

    entity_description: GreeBinarySensorEntityDescription

    def __init__(self, coordinator, description: GreeBinarySensorEntityDescription) -> None:
        """Initialize the Gree device."""
        self.entity_description = description

        super().__init__(coordinator, description.key)

    @property
    def is_on(self) -> bool:
        """Return if the state is turned on."""
        return self.entity_description.get_value_fn(self.coordinator.device)