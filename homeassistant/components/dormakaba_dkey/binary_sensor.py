"""Dormakaba dKey integration binary sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from py_dormakaba_dkey import DKEYLock
from py_dormakaba_dkey.commands import DoorPosition, Notifications, UnlockStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import DormakabaDkeyEntity
from .models import DormakabaDkeyData


@dataclass
class DormakabaDkeyBinarySensorDescriptionMixin:
    """Class for keys required by Dormakaba dKey binary sensor entity."""

    is_on: Callable[[Notifications], bool]


@dataclass
class DormakabaDkeyBinarySensorDescription(
    BinarySensorEntityDescription, DormakabaDkeyBinarySensorDescriptionMixin
):
    """Describes Dormakaba dKey binary sensor entity."""


BINARY_SENSOR_DESCRIPTIONS = (
    DormakabaDkeyBinarySensorDescription(
        key="door_position",
        name="Door",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on=lambda state: state.door_position == DoorPosition.OPEN,
    ),
    DormakabaDkeyBinarySensorDescription(
        key="security_locked",
        name="Dead bolt",
        device_class=BinarySensorDeviceClass.LOCK,
        is_on=lambda state: state.unlock_status != UnlockStatus.SECURITY_LOCKED,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform for Dormakaba dKey."""
    data: DormakabaDkeyData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DormakabaDkeyBinarySensor(data.coordinator, data.lock, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class DormakabaDkeyBinarySensor(DormakabaDkeyEntity, BinarySensorEntity):
    """Dormakaba dKey binary sensor."""

    _attr_has_entity_name = True
    entity_description: DormakabaDkeyBinarySensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[None],
        lock: DKEYLock,
        description: DormakabaDkeyBinarySensorDescription,
    ) -> None:
        """Initialize a Dormakaba dKey binary sensor."""
        self.entity_description = description
        self._attr_unique_id = f"{lock.address}_{description.key}"
        super().__init__(coordinator, lock)

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_is_on = self.entity_description.is_on(self._lock.state)
