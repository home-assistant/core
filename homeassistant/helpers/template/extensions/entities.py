"""Entity functions for Home Assistant templates."""

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID, CONF_EXCLUDE, ENTITY_MATCH_ALL
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
                TemplateFunction(
                    "resolve_target",
                    self.resolve_target,
                    as_global=True,
                    as_filter=True,
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

    def resolve_target(
        self,
        target_dict: Any,
        expand_group: bool = True,
        primary_entities_only: bool = True,
    ) -> Iterable[str]:
        """Resolve a target mapping into entity IDs."""
        if not isinstance(target_dict, Mapping):
            return []

        from homeassistant.helpers import config_validation as cv, target  # noqa: PLC0415

        target_config = dict(target_dict)

        def _normalize_entity_ids(config: dict[str, Any]) -> None:
            if ATTR_ENTITY_ID not in config:
                return
            entity_ids = cv.comp_entity_ids_or_uuids(config[ATTR_ENTITY_ID])
            if isinstance(entity_ids, list):
                entity_ids = er.async_validate_entity_ids(
                    er.async_get(self.hass), entity_ids
                )
            config[ATTR_ENTITY_ID] = entity_ids

        _normalize_entity_ids(target_config)
        if (exclude_config := target_config.get(CONF_EXCLUDE)) is not None:
            exclude_config = dict(exclude_config)
            _normalize_entity_ids(exclude_config)
            target_config[CONF_EXCLUDE] = exclude_config

        target_selection = target.TargetSelection(target_config)
        if not target_selection.has_any_target:
            return []

        if target_config.get(ATTR_ENTITY_ID) == ENTITY_MATCH_ALL:
            excluded = target.async_extract_excluded_entity_ids(
                self.hass, target_selection, expand_group
            )
            return [
                entity_id
                for entity_id in self.hass.states.async_entity_ids()
                if entity_id not in excluded
            ]

        selected = target.async_extract_referenced_entity_ids(
            self.hass,
            target_selection,
            expand_group=expand_group,
            primary_entities_only=primary_entities_only,
        )

        return list(selected.referenced | selected.indirectly_referenced)
