"""Config entry functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import TemplateError
from homeassistant.helpers import entity_registry as er

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class ConfigEntryExtension(BaseTemplateExtension):
    """Jinja2 extension for config entry functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the config entry extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "integration_entities",
                    self.integration_entities,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "config_entry_id",
                    self.config_entry_id,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "config_entry_attr",
                    self.config_entry_attr,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
            ],
        )

    def integration_entities(self, entry_name: str) -> Iterable[str]:
        """Get entity IDs for entities tied to an integration/domain.

        Provide entry_name as domain to get all entity IDs for an integration/domain
        or provide a config entry title for filtering between instances of the same
        integration.
        """
        # Don't allow searching for config entries without title
        if not entry_name:
            return []

        hass = self.hass

        # first try if there are any config entries with a matching title
        entities: list[str] = []
        ent_reg = er.async_get(hass)
        for entry in hass.config_entries.async_entries():
            if entry.title != entry_name:
                continue
            entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
            entities.extend(entry.entity_id for entry in entries)
        if entities:
            return entities

        # fallback to just returning all entities for a domain
        from homeassistant.helpers.entity import entity_sources  # noqa: PLC0415

        return [
            entity_id
            for entity_id, info in entity_sources(hass).items()
            if info["domain"] == entry_name
        ]

    def config_entry_id(self, entity_id: str) -> str | None:
        """Get a config entry ID from an entity ID."""
        entity_reg = er.async_get(self.hass)
        if entity := entity_reg.async_get(entity_id):
            return entity.config_entry_id
        return None

    def config_entry_attr(self, config_entry_id: str, attr_name: str) -> Any:
        """Get config entry specific attribute."""
        if not isinstance(config_entry_id, str):
            raise TemplateError("Must provide a config entry ID")

        if attr_name not in (
            "domain",
            "title",
            "state",
            "source",
            "disabled_by",
            "pref_disable_polling",
        ):
            raise TemplateError("Invalid config entry attribute")

        config_entry = self.hass.config_entries.async_get_entry(config_entry_id)

        if config_entry is None:
            return None

        return getattr(config_entry, attr_name)
