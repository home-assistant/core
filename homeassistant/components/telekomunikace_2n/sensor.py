"""2N Telekomunikace sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from py2n import Py2NDeviceData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Py2NDeviceCoordinator
from .const import DATA_CONFIG_ENTRY, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class Py2NDeviceSensorRequiredKeysMixin:
    """Class for 2N entity required keys."""

    value: Callable[[Py2NDeviceData], Any]


@dataclass
class Py2NDeviceSensorEntityDescription(
    SensorEntityDescription, Py2NDeviceSensorRequiredKeysMixin
):
    """A class that describes sensor entities."""


SENSOR_TYPES: tuple[Py2NDeviceSensorEntityDescription, ...] = (
    Py2NDeviceSensorEntityDescription(
        key="uptime",
        name="uptime",
        entity_registry_enabled_default=True,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.uptime,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id]

    sensors = []

    device_info = DeviceInfo(
        configuration_url=f"https://{entry.data[CONF_HOST]}/",
        identifiers={(DOMAIN, coordinator.data.serial)},
        manufacturer="2N Telekomunikace",
        model=coordinator.data.model,
        name=coordinator.data.name,
        sw_version=coordinator.data.firmware,
        hw_version=coordinator.data.hardware,
    )

    for description in SENSOR_TYPES:
        if description.value(coordinator.data) is not None:
            sensors.append(Py2NDeviceSensor(coordinator, description, device_info))
    async_add_entities(sensors, False)


class Py2NDeviceSensor(CoordinatorEntity[Py2NDeviceCoordinator], SensorEntity):
    """Define a 2N sensor."""

    _attr_has_entity_name = True
    entity_description: Py2NDeviceSensorEntityDescription

    def __init__(
        self,
        coordinator: Py2NDeviceCoordinator,
        description: Py2NDeviceSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = device_info
        self._attr_native_value = description.value(coordinator.data)
        self._attr_unique_id = f"{coordinator.data.serial.lower()}_{description.key}"
        self.entity_description = description

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.entity_description.value(self.coordinator.data)
        self.async_write_ha_state()
