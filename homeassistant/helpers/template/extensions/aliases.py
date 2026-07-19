"""Alias functions for Home Assistant templates."""

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    floor_registry as fr,
)

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class AliasExtension(BaseTemplateExtension):
    """Extension for alias-related template functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the alias extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "aliases",
                    self.aliases,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
            ],
        )

    def aliases(self, lookup_value: Any) -> list[str]:
        """Return the aliases of an entity, area, or floor ID.

        Dispatch mirrors ``labels()``: the entity ID is shape-checked with
        ``cv.entity_id`` first, then the value is tried as an area ID and finally
        a floor ID, first hit wins. Area and floor IDs are both bare slugs and
        cannot be told apart by shape, so area-before-floor is the deterministic
        tiebreak. Returns an empty list when nothing matches.
        """
        lookup_value = str(lookup_value)

        # Import here, not at top-level to avoid circular import
        from homeassistant.helpers import config_validation as cv  # noqa: PLC0415

        try:
            cv.entity_id(lookup_value)
        except vol.Invalid:
            pass
        else:
            if entity := er.async_get(self.hass).async_get(lookup_value):
                # entity.aliases may hold a non-str ComputedNameType sentinel
                return sorted(a for a in entity.aliases if isinstance(a, str))

        if area := ar.async_get(self.hass).async_get_area(lookup_value):
            return sorted(area.aliases)

        if floor := fr.async_get(self.hass).async_get_floor(lookup_value):
            return sorted(floor.aliases)

        return []
