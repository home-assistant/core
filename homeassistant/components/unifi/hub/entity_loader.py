"""UniFi Network entity loader.

Central point to load entities for the different platforms.
Make sure expected clients are available for platforms.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING

from aiounifi.interfaces.api_handlers import ItemEvent

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..entity import UnifiEntity, UnifiEntityDescription

if TYPE_CHECKING:
    from .hub import UnifiHub

CHECK_HEARTBEAT_INTERVAL = timedelta(seconds=1)


class UnifiEntityLoader:
    """UniFi Network integration handling platforms for entity registration."""

    def __init__(self, hub: UnifiHub) -> None:
        """Initialize the UniFi entity loader."""
        self.hub = hub

        self.platforms: list[
            tuple[
                AddEntitiesCallback,
                type[UnifiEntity],
                tuple[UnifiEntityDescription, ...],
                bool,
            ]
        ] = []

        self.known_objects: set[tuple[str, str]] = set()
        """Tuples of entity description key and object ID of loaded entities."""

    @callback
    def register_platform(
        self,
        async_add_entities: AddEntitiesCallback,
        entity_class: type[UnifiEntity],
        descriptions: tuple[UnifiEntityDescription, ...],
        requires_admin: bool = False,
    ) -> None:
        """Register UniFi entity platforms."""
        self.platforms.append(
            (async_add_entities, entity_class, descriptions, requires_admin)
        )

    @callback
    def load_entities(self) -> None:
        """Populate UniFi platforms with entities."""
        for (
            async_add_entities,
            entity_class,
            descriptions,
            requires_admin,
        ) in self.platforms:
            if requires_admin and not self.hub.is_admin:
                continue
            self._load_entities(entity_class, descriptions, async_add_entities)

    @callback
    def _should_add_entity(
        self, description: UnifiEntityDescription, obj_id: str
    ) -> bool:
        """Check if entity should be added."""
        return bool(
            (description.key, obj_id) not in self.known_objects
            and description.allowed_fn(self.hub, obj_id)
            and description.supported_fn(self.hub, obj_id)
        )

    @callback
    def _load_entities(
        self,
        unifi_platform_entity: type[UnifiEntity],
        descriptions: tuple[UnifiEntityDescription, ...],
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Subscribe to UniFi API handlers and create entities."""

        @callback
        def async_load_entities(descriptions: Iterable[UnifiEntityDescription]) -> None:
            """Load and subscribe to UniFi endpoints."""

            @callback
            def _add_unifi_entities() -> None:
                """Add UniFi entity."""
                async_add_entities(
                    unifi_platform_entity(obj_id, self.hub, description)
                    for description in descriptions
                    for obj_id in description.api_handler_fn(self.hub.api)
                    if self._should_add_entity(description, obj_id)
                )

            _add_unifi_entities()

            @callback
            def _create_unifi_entity(
                description: UnifiEntityDescription, event: ItemEvent, obj_id: str
            ) -> None:
                """Create new UniFi entity on event."""
                if self._should_add_entity(description, obj_id):
                    async_add_entities(
                        [unifi_platform_entity(obj_id, self.hub, description)]
                    )

            for description in descriptions:
                description.api_handler_fn(self.hub.api).subscribe(
                    partial(_create_unifi_entity, description), ItemEvent.ADDED
                )

            self.hub.config.entry.async_on_unload(
                async_dispatcher_connect(
                    self.hub.hass,
                    self.hub.signal_options_update,
                    _add_unifi_entities,
                )
            )

        async_load_entities(descriptions)
