"""Axis network device entity loader.

Central point to load entities for the different platforms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axis.models.event import Event, EventOperation, EventTopic

from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..entity import AxisEventDescription, AxisEventEntity

if TYPE_CHECKING:
    from .hub import AxisHub


class AxisEntityLoader:
    """Axis network device integration handling platforms for entity registration."""

    def __init__(self, hub: AxisHub) -> None:
        """Initialize the Axis entity loader."""
        self.hub = hub

        self.registered_events: set[tuple[str, EventTopic, str]] = set()
        self.topic_to_entity: dict[
            EventTopic,
            list[
                tuple[
                    AddEntitiesCallback,
                    type[AxisEventEntity],
                    AxisEventDescription,
                ]
            ],
        ] = {}

    @callback
    def register_platform(
        self,
        async_add_entities: AddEntitiesCallback,
        entity_class: type[AxisEventEntity],
        descriptions: tuple[AxisEventDescription, ...],
    ) -> None:
        """Register Axis entity platforms."""
        topics: tuple[EventTopic, ...]
        for description in descriptions:
            if isinstance(description.event_topic, EventTopic):
                topics = (description.event_topic,)
            else:
                topics = description.event_topic
            for topic in topics:
                self.topic_to_entity.setdefault(topic, []).append(
                    (async_add_entities, entity_class, description)
                )

    @callback
    def _create_entities_from_event(self, event: Event) -> None:
        """Create Axis entities from event."""
        event_id = (event.topic, event.topic_base, event.id)
        if event_id in self.registered_events:
            # Device has restarted and all events are initialized anew
            return
        self.registered_events.add(event_id)
        for (
            async_add_entities,
            entity_class,
            description,
        ) in self.topic_to_entity[event.topic_base]:
            if not description.supported_fn(self.hub, event):
                continue
            async_add_entities([entity_class(self.hub, description, event)])

    @callback
    def initialize_platforms(self) -> None:
        """Prepare event listener that can populate platform entities."""
        self.hub.api.event.subscribe(
            self._create_entities_from_event,
            topic_filter=tuple(self.topic_to_entity.keys()),
            operation_filter=EventOperation.INITIALIZED,
        )
