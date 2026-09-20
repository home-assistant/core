"""Event platform for Portainer."""

from datetime import datetime
from typing import override

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PortainerConfigEntry
from .const import CONTAINER_STATE_EVENT_TYPES
from .coordinator import PortainerContainerData, PortainerCoordinator
from .entity import PortainerContainerEntity, PortainerCoordinatorData

PARALLEL_UPDATES = 0

CONTAINER_EVENT_DESCRIPTION = EventEntityDescription(
    key="docker_event",
    translation_key="docker_event",
    entity_category=EntityCategory.DIAGNOSTIC,
    event_types=list(CONTAINER_STATE_EVENT_TYPES),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer event entities."""
    coordinator = entry.runtime_data

    def _async_add_new_containers(
        containers: list[tuple[PortainerCoordinatorData, PortainerContainerData]],
    ) -> None:
        """Add new container event entities."""
        async_add_entities(
            PortainerContainerEventEntity(
                coordinator, CONTAINER_EVENT_DESCRIPTION, container, endpoint
            )
            for (endpoint, container) in containers
        )

    coordinator.new_containers_callbacks.append(_async_add_new_containers)
    _async_add_new_containers(
        [
            (endpoint, container)
            for endpoint in coordinator.data.values()
            for container in endpoint.containers.values()
        ]
    )


class PortainerContainerEventEntity(PortainerContainerEntity, EventEntity):
    """Representation of Docker lifecycle events for a Portainer container."""

    entity_description: EventEntityDescription
    coordinator: PortainerCoordinator

    @override
    def _handle_coordinator_update(self) -> None:
        """Fire an event if the container reported a new Docker event."""
        if (
            self.available
            and (last_event := self.container_data.last_docker_event) is not None
        ):
            last_triggered = self.state
            if (
                last_triggered is None
                or datetime.fromisoformat(last_triggered) < last_event.occurred_at
            ):
                self._trigger_event(last_event.action)
        super()._handle_coordinator_update()
