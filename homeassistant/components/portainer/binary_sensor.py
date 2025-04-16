"""Binary sensor platform for Portainer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pyportainer.models.docker import DockerContainer

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

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
    attributes_fn: Callable[[Any], dict[Any, StateType]] | None = None


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
    portainer = entry.runtime_data.coordinator
    entities: list[BinarySensorEntity] = []

    for endpoint in portainer.endpoints.values():
        entities.extend(
            [
                PortainerEndpointSensor(
                    coordinator=portainer,
                    entry=entry,
                    entity_description=entity_description,
                    device_info=endpoint,
                )
                for entity_description in ENDPOINT_SENSORS
            ]
        )

        for container in endpoint.containers.values():
            entities.extend(
                [
                    PortainerContainerSensor(
                        coordinator=portainer,
                        entry=entry,
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
        entry: PortainerConfigEntry,
        entity_description: PortainerBinarySensorEntityDescription,
        device_info: PortainerCoordinatorData,
    ) -> None:
        """Initialize Portainer endpoint binary sensor entity."""
        self.entity_description = entity_description
        super().__init__(device_info, entry, coordinator)

        self._attr_unique_id = f"{entity_description.key} {device_info.id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            assert self.device_id in self.coordinator.endpoints
            self._device_info = self.coordinator.endpoints[self.device_id]
        except KeyError:
            return

        self._attr_is_on = self.entity_description.state_fn(self._device_info)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                self._device_info
            )
        super()._handle_coordinator_update()


class PortainerContainerSensor(PortainerContainerEntity, BinarySensorEntity):
    """Representation of a Portainer container sensor."""

    entity_description: PortainerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entry: PortainerConfigEntry,
        entity_description: PortainerBinarySensorEntityDescription,
        device_info: DockerContainer,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer container sensor."""
        self.entity_description = entity_description
        super().__init__(device_info, entry, coordinator, via_device)

        self._attr_unique_id = f"{entity_description.key} {device_info.id}"

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        try:
            self._device_info = self.coordinator.endpoints[self.endpoint_id].containers[
                self.device_id
            ]
        except (KeyError, IndexError):
            return

        self._attr_is_on = self.entity_description.state_fn(self._device_info)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                self._device_info
            )

        super()._handle_coordinator_update()
