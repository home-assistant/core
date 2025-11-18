"""Helper for groups."""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.core import HomeAssistant, callback

from .singleton import singleton

if TYPE_CHECKING:
    from .entity import Entity

DATA_GROUP_ENTITIES = "group_entities"
ENTITY_PREFIX = "group."


class GroupType(Enum):
    """Type of group entity."""

    GENERIC = "generic"
    INTEGRATION_SPECIFIC = "integration_specific"


@callback
@singleton(DATA_GROUP_ENTITIES)
def get_group_entities(hass: HomeAssistant) -> dict[str, Entity]:
    """Get the group entities.

    Items are added to this dict by Entity.async_internal_added_to_hass and
    removed by Entity.async_internal_will_remove_from_hass.
    """
    return {}


def expand_entity_ids(hass: HomeAssistant, entity_ids: Iterable[Any]) -> list[str]:
    """Return entity_ids with group entity ids replaced by their members.

    Async friendly.
    """
    group_entities = get_group_entities(hass)

    found_ids: list[str] = []
    for entity_id in entity_ids:
        if not isinstance(entity_id, str) or entity_id in (
            ENTITY_MATCH_NONE,
            ENTITY_MATCH_ALL,
        ):
            continue

        entity_id = entity_id.lower()

        # If entity_id points at a group, expand it
        if (entity := group_entities.get(entity_id)) is not None and (
            entity.group_type is GroupType.GENERIC
        ):
            child_entities = entity.included_entity_ids
            if entity_id in child_entities:
                child_entities = list(child_entities)
                child_entities.remove(entity_id)
            found_ids.extend(
                ent_id
                for ent_id in expand_entity_ids(hass, child_entities)
                if ent_id not in found_ids
            )
        # If entity_id points at an old-style group, expand it
        elif entity_id.startswith(ENTITY_PREFIX):
            child_entities = get_entity_ids(hass, entity_id)
            if entity_id in child_entities:
                child_entities = list(child_entities)
                child_entities.remove(entity_id)
            found_ids.extend(
                ent_id
                for ent_id in expand_entity_ids(hass, child_entities)
                if ent_id not in found_ids
            )
        elif entity_id not in found_ids:
            found_ids.append(entity_id)

    return found_ids


def get_entity_ids(
    hass: HomeAssistant, entity_id: str, domain_filter: str | None = None
) -> list[str]:
    """Get members of this group.

    Async friendly.
    """
    group = hass.states.get(entity_id)
    if not group or ATTR_ENTITY_ID not in group.attributes:
        return []
    entity_ids: list[str] = group.attributes[ATTR_ENTITY_ID]
    if not domain_filter:
        return entity_ids
    domain_filter = f"{domain_filter.lower()}."
    return [ent_id for ent_id in entity_ids if ent_id.startswith(domain_filter)]


def deduplicate_entity_ids(hass: HomeAssistant, entity_ids: list[str]) -> list[str]:
    """Return entity IDs with group entity ids subsuming their members."""
    group_entities = get_group_entities(hass)

    all_child_entity_ids: set[str] = set()

    def _get_all_child_entity_ids_rec(entity_ids: Iterable[str]) -> None:
        nonlocal all_child_entity_ids

        for entity_id in entity_ids:
            if (entity := group_entities.get(entity_id)) is not None and (
                entity.group_type is GroupType.INTEGRATION_SPECIFIC
            ):
                child_entity_ids = [
                    child_entity_id
                    for child_entity_id in entity.included_entity_ids
                    if child_entity_id not in all_child_entity_ids
                ]
                all_child_entity_ids.update(child_entity_ids)
                _get_all_child_entity_ids_rec(child_entity_ids)

    _get_all_child_entity_ids_rec(entity_ids)

    return [
        entity_id for entity_id in entity_ids if entity_id not in all_child_entity_ids
    ]
