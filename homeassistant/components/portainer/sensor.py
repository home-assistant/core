"""Sensor platform for Portainer integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyportainer.models.docker import DockerContainer

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PortainerConfigEntry, PortainerCoordinator
from .entity import PortainerContainerEntity, PortainerCoordinatorData


@dataclass(frozen=True, kw_only=True)
class PortainerSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer sensor description.

    value_fn must return a StateType (str | int | float | None or date/datetime/Decimal),
    but for these container sensors we only return str | None.
    """

    value_fn: Callable[[DockerContainer], StateType]


CONTAINER_SENSORS: tuple[PortainerSensorEntityDescription, ...] = (
    PortainerSensorEntityDescription(
        key="image",
        translation_key="image",
        value_fn=lambda data: data.image,
    ),
    PortainerSensorEntityDescription(
        key="status",
        translation_key="status",
        value_fn=lambda data: data.status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer sensors based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        PortainerContainerSensor(
            coordinator,
            entity_description,
            container,
            endpoint,
        )
        for endpoint in coordinator.data.values()
        for container in endpoint.containers.values()
        for entity_description in CONTAINER_SENSORS
    )


class PortainerContainerSensor(PortainerContainerEntity, SensorEntity):
    """Representation of a Portainer container sensor."""

    entity_description: PortainerSensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerSensorEntityDescription,
        device_info: DockerContainer,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer container sensor."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data[self.endpoint_id].containers[self.device_id]
        )
