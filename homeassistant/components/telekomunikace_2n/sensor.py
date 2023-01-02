"""2N Telekomunikace sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from py2n import Py2NDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import Py2NDeviceCoordinator, Py2NDeviceEntity
from .const import DOMAIN


@dataclass
class Py2NDeviceSensorRequiredKeysMixin:
    """Class for 2N entity required keys."""

    value: Callable[[Py2NDevice], StateType | datetime]


@dataclass
class Py2NDeviceSensorEntityDescription(
    SensorEntityDescription, Py2NDeviceSensorRequiredKeysMixin
):
    """A class that describes sensor entities."""


SENSOR_TYPES: tuple[Py2NDeviceSensorEntityDescription, ...] = (
    Py2NDeviceSensorEntityDescription(
        key="uptime",
        name="Uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda device: cast(datetime, device.data.uptime),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: Py2NDeviceCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for description in SENSOR_TYPES:
        if description.value(coordinator.device) is not None:
            sensors.append(
                Py2NDeviceSensor(coordinator, description, coordinator.device)
            )
    async_add_entities(sensors, False)


class Py2NDeviceSensor(Py2NDeviceEntity, SensorEntity):
    """Define a 2N Telekomunikace sensor."""

    entity_description: Py2NDeviceSensorEntityDescription

    def __init__(
        self,
        coordinator: Py2NDeviceCoordinator,
        description: Py2NDeviceSensorEntityDescription,
        device: Py2NDevice,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description, device)

    @property
    def native_value(self) -> StateType | datetime:
        """Native value."""
        return self.entity_description.value(self.device)
