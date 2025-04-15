"""Sensors for the endpoints and containers in Portainer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PortainerConfigEntry
from .coordinator import (
    PortainerCoordinator,
    PortainerCoordinatorData,  # Import the correct type
)
from .entity import PortainerEndpointEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PortainerSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer sensor description."""

    state_fn: Callable[[Any], StateType]
    attributes_fn: Callable[[Any], dict[Any, StateType]] | None = None
    data_category: str | None = None


def get_type(data: PortainerCoordinatorData) -> str:
    """Return the type of the endpoint."""
    assert data.endpoint.type in (1, 2, 3), "Invalid endpoint type"
    return {
        1: "Docker",
        2: "Docker Agent",
        3: "Azure",
    }.get(data.endpoint.type, "Unknown")


UTILIZATION_SENSORS: tuple[PortainerSensorEntityDescription, ...] = (
    PortainerSensorEntityDescription(
        key="type",
        translation_key="type",
        icon="mdi:server",
        state_fn=get_type,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer sensors."""
    portainer = entry.runtime_data.coordinator
    entities: list[SensorEntity] = []

    for endpoint in portainer.endpoints.values():
        entities.extend(
            [
                PortainerEndpointSensor(
                    coordinator=portainer,
                    entry=entry,
                    entity_description=entity_description,
                    device_info=endpoint,
                )
                for entity_description in UTILIZATION_SENSORS
            ]
        )

    async_add_entities(entities, True)


class PortainerEndpointSensor(PortainerEndpointEntity, SensorEntity):
    """Representation of a Portainer endpoints."""

    entity_description: PortainerSensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entry: PortainerConfigEntry,
        entity_description: PortainerSensorEntityDescription,
        device_info: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer endpoint sensor."""
        self.entity_description = entity_description
        super().__init__(device_info, entry, coordinator)

        self._attr_unique_id = f"{entity_description.key} {device_info.id}"

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        try:
            assert self.device_id in self.coordinator.endpoints
            self._device_info = self.coordinator.endpoints[self.device_id]
        except KeyError:
            return

        self._attr_native_value = self.entity_description.state_fn(self._device_info)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                self._device_info
            )

        super()._handle_coordinator_update()
