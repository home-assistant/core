"""Binary sensor platform for Portainer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from pyportainer.models.docker import DockerContainer

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PortainerConfigEntry
from .coordinator import PortainerCoordinator
from .entity import (
    PortainerContainerEntity,
    PortainerCoordinatorData,
    PortainerEndpointEntity,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PortainerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Portainer binary sensor description."""

    state_fn: Callable[[Any], bool]


CONTAINER_SENSORS: tuple[PortainerBinarySensorEntityDescription, ...] = (
    PortainerBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.state == "running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ENDPOINT_SENSORS: tuple[PortainerBinarySensorEntityDescription, ...] = (
    PortainerBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.endpoint.status == 1,  # 1 = Running | 2 = Stopped
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer binary sensors."""
    coordinator = entry.runtime_data
    known_endpoints: set[int] = set()
    known_containers: set[tuple[int, str]] = set()

    def _check_devices() -> None:
        """Check for new endpoints and/or containers and add them."""
        entities: list[BinarySensorEntity] = []
        current_endpoints = set(coordinator.data)
        new_endpoints = current_endpoints - known_endpoints
        if new_endpoints:
            known_endpoints.update(new_endpoints)
            entities.extend(
                PortainerEndpointSensor(
                    coordinator,
                    entity_description,
                    endpoint,
                )
                for endpoint in coordinator.data.values()
                if endpoint.id in new_endpoints
                for entity_description in ENDPOINT_SENSORS
            )

        current_containers = {
            (endpoint.id, container.id)
            for endpoint in coordinator.data.values()
            for container in endpoint.containers.values()
        }
        new_containers = current_containers - known_containers
        if new_containers:
            _LOGGER.debug("New containers found: %s", new_containers)
            known_containers.update(new_containers)
            entities.extend(
                PortainerContainerSensor(
                    coordinator,
                    entity_description,
                    container,
                    endpoint,
                )
                for endpoint in coordinator.data.values()
                for container in endpoint.containers.values()
                if (endpoint.id, container.id) in new_containers
                for entity_description in CONTAINER_SENSORS
            )

        if entities:
            async_add_entities(entities)

    _check_devices()
    entry.async_on_unload(coordinator.async_add_listener(_check_devices))


class PortainerEndpointSensor(PortainerEndpointEntity, BinarySensorEntity):
    """Representation of a Portainer endpoint binary sensor entity."""

    entity_description: PortainerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerBinarySensorEntityDescription,
        device_info: PortainerCoordinatorData,
    ) -> None:
        """Initialize Portainer endpoint binary sensor entity."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_info.id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.device_id in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.coordinator.data[self.device_id])


class PortainerContainerSensor(PortainerContainerEntity, BinarySensorEntity):
    """Representation of a Portainer container sensor."""

    entity_description: PortainerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerBinarySensorEntityDescription,
        device_info: DockerContainer,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer container sensor."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.endpoint_id in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(
            self.coordinator.data[self.endpoint_id].containers[self.device_name]
        )
