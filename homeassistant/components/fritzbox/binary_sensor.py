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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FritzboxConfigEntry
from .entity import FritzBoxDeviceEntity
from .model import FritzEntityDescriptionMixinBase


@dataclass(frozen=True, kw_only=True)
class FritzBinarySensorEntityDescription(
    BinarySensorEntityDescription, FritzEntityDescriptionMixinBase
):
    """Description for Fritz!Smarthome binary sensor entities."""

    is_on: Callable[[FritzhomeDevice], bool | None]


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
    hass: HomeAssistant,
    entry: FritzboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the FRITZ!SmartHome binary sensor from ConfigEntry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities(devices: set[str] | None = None) -> None:
        """Add devices."""
        if devices is None:
            devices = coordinator.new_devices
        if not devices:
            return
        async_add_entities(
            FritzboxBinarySensor(coordinator, ain, description)
            for ain in devices
            for description in BINARY_SENSOR_TYPES
            if description.suitable(coordinator.data.devices[ain])
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities(set(coordinator.data.devices))


class FritzboxBinarySensor(FritzBoxDeviceEntity, BinarySensorEntity):
    """Representation of a binary FRITZ!SmartHome device."""

    entity_description: FritzBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self.entity_description.is_on(self.data)
