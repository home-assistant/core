"""Entity functions for Home Assistant templates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class EntityExtension(BaseTemplateExtension):
    """Jinja2 extension for entity functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the entity extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "entity_name",
                    self.entity_name,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "is_hidden_entity",
                    self.is_hidden_entity,
                    as_global=True,
                    as_test=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
            ],
        )

    def entity_name(self, entity_id: str) -> str | None:
        """Get the name of an entity from its entity ID."""
        ent_reg = er.async_get(self.hass)
        if (entry := ent_reg.async_get(entity_id)) is not None:
            return er.async_get_unprefixed_name(self.hass, entry)

        # Fall back to state for entities without a unique_id (not in the registry)
        if (state := self.hass.states.get(entity_id)) is not None:
            return state.name

        return None

    def is_hidden_entity(self, entity_id: str) -> bool:
        """Test if an entity is hidden."""
        entity_reg = er.async_get(self.hass)
        entry = entity_reg.async_get(entity_id)
        return entry is not None and entry.hidden
