"""Reads vehicle status from StarLine API."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity


@dataclass
class StarlineRequiredKeysMixin:
    """Mixin for required keys."""

    name_: str


@dataclass
class StarlineBinarySensorEntityDescription(
    BinarySensorEntityDescription, StarlineRequiredKeysMixin
):
    """Describes Starline binary_sensor entity."""


BINARY_SENSOR_TYPES: tuple[StarlineBinarySensorEntityDescription, ...] = (
    StarlineBinarySensorEntityDescription(
        key="hbrake",
        name_="Hand Brake",
        device_class=DEVICE_CLASS_POWER,
    ),
    StarlineBinarySensorEntityDescription(
        key="hood",
        name_="Hood",
        device_class=DEVICE_CLASS_DOOR,
    ),
    StarlineBinarySensorEntityDescription(
        key="trunk",
        name_="Trunk",
        device_class=DEVICE_CLASS_DOOR,
    ),
    StarlineBinarySensorEntityDescription(
        key="alarm",
        name_="Alarm",
        device_class=DEVICE_CLASS_PROBLEM,
    ),
    StarlineBinarySensorEntityDescription(
        key="door",
        name_="Doors",
        device_class=DEVICE_CLASS_LOCK,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine sensors."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = [
        sensor
        for device in account.api.devices.values()
        for description in BINARY_SENSOR_TYPES
        if description.key in device.car_state
        if (sensor := StarlineSensor(account, device, description)).is_on is not None
    ]
    async_add_entities(entities)


class StarlineSensor(StarlineEntity, BinarySensorEntity):
    """Representation of a StarLine binary sensor."""

    entity_description: StarlineBinarySensorEntityDescription

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        description: StarlineBinarySensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(account, device, description.key, description.name_)
        self.entity_description = description

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._device.car_state.get(self._key)
