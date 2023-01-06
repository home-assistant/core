"""Contains base entity classes for Starlink entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from starlink_grpc import StatusDict

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StarlinkUpdateCoordinator


@dataclass
class StarlinkSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[StatusDict], datetime | StateType]


@dataclass
class StarlinkSensorEntityDescription(
    SensorEntityDescription, StarlinkSensorEntityDescriptionMixin
):
    """Describes a Starlink sensor entity."""


class StarlinkSensorEntity(CoordinatorEntity[StarlinkUpdateCoordinator], SensorEntity):
    """A SensorEntity that is registered under the Starlink device, and handles creating unique IDs."""

    entity_description: StarlinkSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StarlinkUpdateCoordinator,
        description: StarlinkSensorEntityDescription,
    ) -> None:
        """Initialize the sensor and set the update coordinator."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.coordinator.data['id']}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.data["id"]),
            },
            sw_version=self.coordinator.data["software_version"],
            hw_version=self.coordinator.data["hardware_version"],
            name="Starlink",
            configuration_url=f"http://{self.coordinator.channel_context.target.split(':')[0]}",
            manufacturer="SpaceX",
            model="Starlink",
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Calculate the sensor value from the entity description."""
        return self.entity_description.value_fn(self.coordinator.data)
