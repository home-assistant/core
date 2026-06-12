"""Template functions for exposed entities."""

from collections.abc import Iterable
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
        """Return entity IDs for all entities exposed to the conversation integration."""
        # Imported here to avoid a circular import at module load time, as this
        # extension is imported very early during bootstrap.
        from homeassistant.components import conversation  # noqa: PLC0415
        from homeassistant.components.homeassistant.exposed_entities import (  # noqa: PLC0415
            async_should_expose,
        )

        return [
            entry.entity_id
            for entry in er.async_get(self.hass).entities.values()
            if async_should_expose(self.hass, conversation.DOMAIN, entry.entity_id)
        ]
