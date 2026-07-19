"""Alias function for Home Assistant templates."""

from collections.abc import Iterable
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
    """Extension for the alias template function."""

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

    def aliases(self, lookup_value: Any) -> Iterable[str]:
        """Return the sorted aliases of an entity, area, or floor ID ([] if unknown).

        Area is tried before floor because their IDs are indistinguishable bare
        slugs, so the order is the deterministic tiebreak.
        """
        lookup_value = str(lookup_value)

        # Import here, not at top-level to avoid circular import
        from homeassistant.helpers import config_validation as cv  # noqa: PLC0415

        try:
            entity_id = cv.entity_id(lookup_value)
        except vol.Invalid:
            pass
        else:
            if entity := er.async_get(self.hass).async_get(entity_id):
                # entity.aliases may hold a non-str ComputedNameType sentinel
                return sorted(a for a in entity.aliases if isinstance(a, str))

        if area := ar.async_get(self.hass).async_get_area(lookup_value):
            return sorted(area.aliases)

        if floor := fr.async_get(self.hass).async_get_floor(lookup_value):
            return sorted(floor.aliases)

        return []
