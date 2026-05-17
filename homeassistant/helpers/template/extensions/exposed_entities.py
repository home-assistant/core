"""Template functions for exposed entities."""

from collections.abc import Iterable
from typing import TYPE_CHECKING

from homeassistant.components.homeassistant.exposed_entities import async_should_expose
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
                    "exposed_entities",
                    self.exposed_entities,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
            ],
        )

    def exposed_entities(self, assistant: str) -> Iterable[str]:
        """Return entity IDs for all entities exposed to a particular assistant."""
        return [
            entry.entity_id
            for entry in er.async_get(self.hass).entities.values()
            if async_should_expose(self.hass, assistant, entry.entity_id)
        ]
