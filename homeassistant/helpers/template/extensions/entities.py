"""Entity functions for Home Assistant templates."""

from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.registry import NextNamePart

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

    def entity_name(self, entity_id: str, *, fallback: bool = False) -> str | None:
        """Get the name of an entity from its entity ID.

        With fallback, return the device name when the entity has no name of its own.
        """
        ent_reg = er.async_get(self.hass)
        if (entry := ent_reg.async_get(entity_id)) is not None:
            name = entry.entity_name
            if (
                not name
                and fallback
                and entry.next_name_part is NextNamePart.DEVICE
                and (device_id := entry.device_id) is not None
                and (device := dr.async_get(self.hass).async_get(device_id)) is not None
            ):
                return device.name_by_user or device.name
            return name

        # Fall back to state for entities without a unique_id (not in the registry)
        if (state := self.hass.states.get(entity_id)) is not None:
            return state.name

        return None

    def is_hidden_entity(self, entity_id: str) -> bool:
        """Test if an entity is hidden."""
        entity_reg = er.async_get(self.hass)
        entry = entity_reg.async_get(entity_id)
        return entry is not None and entry.hidden
