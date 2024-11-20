"""Helper for groups."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.core import HomeAssistant

ENTITY_PREFIX = "group."


def expand_entity_ids(hass: HomeAssistant, entity_ids: Iterable[Any]) -> list[str]:
    """Return entity_ids with group entity ids replaced by their members.

    Async friendly.
    """
    found_ids: list[str] = []
    for entity_id in entity_ids:
        if not isinstance(entity_id, str) or entity_id in (
            ENTITY_MATCH_NONE,
            ENTITY_MATCH_ALL,
        ):
            continue

        entity_id = entity_id.lower()
        # If entity_id points at a group, expand it
        if entity_id.startswith(ENTITY_PREFIX):
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
