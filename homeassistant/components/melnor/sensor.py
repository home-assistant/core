"""Sensor support for Melnor Bluetooth water timer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from melnor_bluetooth.device import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .models import MelnorBluetoothBaseEntity, MelnorDataUpdateCoordinator


@dataclass
class MelnorSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    state_fn: Callable[[Device], Any]


@dataclass
class MelnorSensorEntityDescription(
    SensorEntityDescription, MelnorSensorEntityDescriptionMixin
):
    """Describes Melnor sensor entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    coordinator: MelnorDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors: list[MelnorSensorEntityDescription] = [
        MelnorSensorEntityDescription(
            device_class=SensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            key="battery",
            name="Battery",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            state_fn=lambda device: device.battery_level,
        ),
        MelnorSensorEntityDescription(
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="rssi",
            name="RSSI",
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            state_class=SensorStateClass.MEASUREMENT,
            state_fn=lambda device: device.rssi,
        ),
    ]

    async_add_devices(
        MelnorSensorEntity(
            coordinator,
            description,
        )
        for description in sensors
    )


class MelnorSensorEntity(MelnorBluetoothBaseEntity, SensorEntity):
    """Representation of a Melnor sensor."""

    entity_description: MelnorSensorEntityDescription

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        entity_description: MelnorSensorEntityDescription,
    ) -> None:
        """Initialize a sensor for a Melnor device."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{self._device.mac}-{entity_description.key}"

        self.entity_description = entity_description

    @property
    def native_value(self) -> StateType:
        """Return the battery level."""
        return self.entity_description.state_fn(self._device)
