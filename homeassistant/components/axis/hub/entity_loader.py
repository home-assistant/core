"""Axis network device entity loader.

Central point to load entities for the different platforms.
"""
from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from axis.models.event import Event, EventOperation

from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..entity import AxisEventDescription, AxisEventEntity

if TYPE_CHECKING:
    from .hub import AxisHub


class AxisEntityLoader:
    """Axis network device integration handling platforms for entity registration."""

    def __init__(self, hub: AxisHub) -> None:
        """Initialize the UniFi entity loader."""
        self.hub = hub

        self.platforms: list[
            tuple[
                AddEntitiesCallback,
                type[AxisEventEntity],
                tuple[AxisEventDescription, ...],
            ]
        ] = []

    @callback
    def register_platform(
        self,
        async_add_entities: AddEntitiesCallback,
        entity_class: type[AxisEventEntity],
        descriptions: tuple[AxisEventDescription, ...],
    ) -> None:
        """Register Axis entity platforms."""
        self.platforms.append((async_add_entities, entity_class, descriptions))

    @callback
    def initialize_platforms(self) -> None:
        """Prepare event listeners and platforms."""

        @callback
        def load_entities(
            platform_entity: type[AxisEventEntity],
            descriptions: tuple[AxisEventDescription, ...],
            async_add_entities: AddEntitiesCallback,
        ) -> None:
            """Set up listeners for events."""

            @callback
            def create_entity(description: AxisEventDescription, event: Event) -> None:
                """Create Axis entity."""
                if description.supported_fn(self.hub, event):
                    async_add_entities([platform_entity(self.hub, description, event)])

            for description in descriptions:
                self.hub.api.event.subscribe(
                    partial(create_entity, description),
                    topic_filter=description.event_topic,
                    operation_filter=EventOperation.INITIALIZED,
                )

        for async_add_entities, entity_class, descriptions in self.platforms:
            load_entities(entity_class, descriptions, async_add_entities)
