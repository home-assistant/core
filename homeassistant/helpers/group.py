"""Helper for groups."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.core import HomeAssistant

ENTITY_PREFIX = "group."


def expand_entity_ids(hass: HomeAssistant, entity_ids: Iterable[Any]) -> list[str]:
    """Return entity_ids with group entity ids replaced by their members.

    Async friendly.
    """
    result: list[str] = []
    seen: set[str] = set()

    # Initialize a FIFO queue to preserve input order across expansions
    queue: deque[str] = deque(
        entity_id.lower()
        for entity_id in entity_ids
        if isinstance(entity_id, str)
        and entity_id not in (ENTITY_MATCH_NONE, ENTITY_MATCH_ALL)
    )

    while queue:
        entity_id = queue.popleft()

        # If entity_id points at a group, expand it
        if entity_id.startswith(ENTITY_PREFIX):
            child_entities = get_entity_ids(hass, entity_id)
            if entity_id in child_entities:
                # Avoid copying unless necessary
                child_entities = list(child_entities)
                child_entities.remove(entity_id)
            # Normalize children ids and enqueue for further processing
            queue.extend(
                child.lower() for child in child_entities if isinstance(child, str)
            )
            continue

        if entity_id not in seen:
            seen.add(entity_id)
            result.append(entity_id)

    return result


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
    if domain_filter is None:
        return entity_ids
    prefix = f"{domain_filter.lower()}."
    return [ent_id for ent_id in entity_ids if ent_id.startswith(prefix)]
