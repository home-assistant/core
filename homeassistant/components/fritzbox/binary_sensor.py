"""Support for Fritzbox binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from pyfritzhome.fritzhomedevice import FritzhomeDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzBoxDeviceEntity
from .const import CONF_COORDINATOR, DOMAIN
from .coordinator import FritzboxDataUpdateCoordinator
from .model import FritzEntityDescriptionMixinBase


@dataclass
class FritzEntityDescriptionMixinBinarySensor(FritzEntityDescriptionMixinBase):
    """BinarySensor description mixin for Fritz!Smarthome entities."""

    is_on: Callable[[FritzhomeDevice], bool | None]


@dataclass
class FritzBinarySensorEntityDescription(
    BinarySensorEntityDescription, FritzEntityDescriptionMixinBinarySensor
):
    """Description for Fritz!Smarthome binary sensor entities."""


BINARY_SENSOR_TYPES: Final[tuple[FritzBinarySensorEntityDescription, ...]] = (
    FritzBinarySensorEntityDescription(
        key="alarm",
        translation_key="alarm",
        device_class=BinarySensorDeviceClass.WINDOW,
        suitable=lambda device: device.has_alarm,
        is_on=lambda device: device.alert_state,
    ),
    FritzBinarySensorEntityDescription(
        key="lock",
        translation_key="lock",
        device_class=BinarySensorDeviceClass.LOCK,
        entity_category=EntityCategory.DIAGNOSTIC,
        suitable=lambda device: device.lock is not None,
        is_on=lambda device: not device.lock,
    ),
    FritzBinarySensorEntityDescription(
        key="device_lock",
        translation_key="device_lock",
        device_class=BinarySensorDeviceClass.LOCK,
        entity_category=EntityCategory.DIAGNOSTIC,
        suitable=lambda device: device.device_lock is not None,
        is_on=lambda device: not device.device_lock,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome binary sensor from ConfigEntry."""
    coordinator: FritzboxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        CONF_COORDINATOR
    ]

    @callback
    def _add_entities() -> None:
        """Add devices."""
        entities: list[FritzboxBinarySensor] = []
        for ain in coordinator.new_devices:
            if (device := coordinator.data.devices.get(ain)) is None:
                continue
            for description in BINARY_SENSOR_TYPES:
                if description.suitable(device):
                    entities.append(FritzboxBinarySensor(coordinator, ain, description))
        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities()


class FritzboxBinarySensor(FritzBoxDeviceEntity, BinarySensorEntity):
    """Representation of a binary FRITZ!SmartHome device."""

    entity_description: FritzBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self.entity_description.is_on(self.data)
