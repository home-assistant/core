"""Contains base entity classes for Starlink entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DISHY_HARDWARE, DISHY_ID
from .coordinator import StarlinkUpdateCoordinator
from .dish_status import DishyStatus


@dataclass
class StarlinkSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[DishyStatus], datetime | StateType]


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
        self._attr_unique_id = f"{self.coordinator.data.id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Calculate the sensor value from the entity description."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Get a DeviceInfo for Dishy."""
        config_url = f"http://{self.coordinator.channel_context.target.split(':')[0]}"
        return DeviceInfo(
            identifiers={
                (DISHY_ID, self.coordinator.data.id),
                (DISHY_HARDWARE, self.coordinator.data.hardware_version),
            },
            sw_version=self.coordinator.data.software_version,
            hw_version=self.coordinator.data.hardware_version,
            name="Starlink",
            configuration_url=config_url,
            manufacturer="SpaceX",
            model="Starlink",
        )
