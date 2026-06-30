"""Template functions for exposed entities."""

from collections.abc import Iterable
from itertools import chain
from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class ExposedEntitiesExtension(BaseTemplateExtension):
    """Extension for exposed entities template functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the exposed entities extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "assist_exposed_entities",
                    self.assist_exposed_entities,
                    as_global=True,
                    requires_hass=True,
                ),
            ],
        )

    def assist_exposed_entities(self) -> Iterable[str]:
        """Return entity IDs for all entities exposed to Assist."""
        # Imported here to avoid a circular import at module load time, as this
        # extension is imported very early during bootstrap.
        from homeassistant.components.homeassistant.exposed_entities import (  # noqa: PLC0415
            DATA_EXPOSED_ENTITIES,
            async_should_expose,
        )

        exposed_entities = self.hass.data[DATA_EXPOSED_ENTITIES]
        entity_registry = er.async_get(self.hass)
        # Entities tracked by the exposed entities helper may not be in the
        # registry (e.g. legacy entities), so consider both sources.
        return [
            entity_id
            for entity_id in dict.fromkeys(
                chain(exposed_entities.entities, entity_registry.entities)
            )
            if async_should_expose(self.hass, "conversation", entity_id)
        ]
