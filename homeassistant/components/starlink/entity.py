"""Contains base entity classes for Starlink entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from starlink_grpc import AlertDict, ObstructionDict, StatusDict

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StarlinkUpdateCoordinator


@dataclass
class StarlinkBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[tuple[StatusDict, ObstructionDict, AlertDict]], bool | None]


@dataclass
class StarlinkSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[
        [tuple[StatusDict, ObstructionDict, AlertDict]], datetime | StateType
    ]


@dataclass
class StarlinkSensorEntityDescription(
    SensorEntityDescription, StarlinkSensorEntityDescriptionMixin
):
    """Describes a Starlink sensor entity."""


@dataclass
class StarlinkBinarySensorEntityDescription(
    BinarySensorEntityDescription, StarlinkBinarySensorEntityDescriptionMixin
):
    """Describes a Starlink binary sensor entity."""


class StarlinkEntity(CoordinatorEntity[StarlinkUpdateCoordinator], Entity):
    """A base Entity that is registered under a Starlink device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StarlinkUpdateCoordinator,
    ) -> None:
        """Initialize the device info and set the update coordinator."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.data[0]["id"]),
            },
            sw_version=self.coordinator.data[0]["software_version"],
            hw_version=self.coordinator.data[0]["hardware_version"],
            name="Starlink",
            configuration_url=f"http://{self.coordinator.channel_context.target.split(':')[0]}",
            manufacturer="SpaceX",
            model="Starlink",
        )


class StarlinkSensorEntity(StarlinkEntity, SensorEntity):
    """A SensorEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkSensorEntityDescription

    def __init__(
        self,
        coordinator: StarlinkUpdateCoordinator,
        description: StarlinkSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.coordinator.data[0]['id']}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Calculate the sensor value from the entity description."""
        return self.entity_description.value_fn(self.coordinator.data)


class StarlinkBinarySensorEntity(StarlinkEntity, BinarySensorEntity):
    """A BinarySensorEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: StarlinkUpdateCoordinator,
        description: StarlinkBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.coordinator.data[0]['id']}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Calculate the dinary sensor value from the entity description."""
        return self.entity_description.value_fn(self.coordinator.data)
