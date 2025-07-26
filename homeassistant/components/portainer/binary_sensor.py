"""Binary sensor platform for Portainer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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


@dataclass(frozen=True, kw_only=True)
class PortainerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Portainer binary sensor description."""

    state_fn: Callable[[Any], bool | None]


CONTAINER_SENSORS: tuple[PortainerBinarySensorEntityDescription, ...] = (
    PortainerBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: bool(data.state == "running"),
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ENDPOINT_SENSORS: tuple[PortainerBinarySensorEntityDescription, ...] = (
    PortainerBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: bool(
            data.endpoint.status == 1
        ),  # 1 = Running | 2 = Stopped
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
    entities: list[BinarySensorEntity] = []

    for endpoint in coordinator.data.values():
        entities.extend(
            [
                PortainerEndpointSensor(
                    coordinator=coordinator,
                    entity_description=entity_description,
                    device_info=endpoint,
                )
                for entity_description in ENDPOINT_SENSORS
            ]
        )

        assert endpoint.containers
        for container in endpoint.containers.values():
            entities.extend(
                [
                    PortainerContainerSensor(
                        coordinator=coordinator,
                        entity_description=entity_description,
                        device_info=container,
                        via_device=endpoint,
                    )
                    for entity_description in CONTAINER_SENSORS
                ]
            )

    async_add_entities(entities, True)


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
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if TYPE_CHECKING:
            assert self.device_id

        return (
            self.entity_description.state_fn(device_info)
            if (device_info := self.coordinator.data.get(self.device_id))
            else None
        )


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

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_info.id}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if TYPE_CHECKING:
            assert self.device_id
            assert self.endpoint_id

        return (
            self.entity_description.state_fn(device_info)
            if (
                device_info := self.coordinator.data[self.endpoint_id].containers.get(
                    self.device_id
                )
            )
            else None
        )
