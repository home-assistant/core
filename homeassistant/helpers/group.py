"""Helper for groups."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from propcache.api import cached_property

from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.core import Event, HomeAssistant, callback

from . import entity_registry as er
from .singleton import singleton

if TYPE_CHECKING:
    from .entity import Entity

DATA_GROUP_ENTITIES = "group_entities"
ENTITY_PREFIX = "group."


class Group:
    """A group base class."""

    @property
    def included_entity_ids(self) -> list[str]:
        """Return the list of entity IDs."""
        raise NotImplementedError

    @callback
    def async_added_to_hass(self, entity: Entity) -> None:
        """Handle when the entity is added to hass."""
        get_group_entities(entity.hass)[entity.entity_id] = entity

    @callback
    def async_will_remove_from_hass(self, entity: Entity) -> None:
        """Handle when the entity will be removed from hass."""
        del get_group_entities(entity.hass)[entity.entity_id]


class GenericGroup(Group):
    """A generic group."""

    def __init__(self, included_entity_ids: list[str]) -> None:
        """Initialize the group."""
        self._included_entity_ids = included_entity_ids

    @cached_property
    def included_entity_ids(self) -> list[str]:
        """Return the list of entity IDs."""
        return self._included_entity_ids


class IntegrationSpecificGroup(Group):
    """An integration-specific group."""

    included_unique_ids: list[str]

    _entity: Entity
    _included_entity_ids: list[str] | None = None

    def __init__(self, included_unique_ids: list[str]) -> None:
        """Initialize the group."""
        self.included_unique_ids = included_unique_ids

    @property
    def included_entity_ids(self) -> list[str]:
        """Return the list of entity IDs."""
        entity_registry = er.async_get(self._entity.hass)
        self._included_entity_ids = [
            entity_id
            for unique_id in self.included_unique_ids
            if (
                entity_id := entity_registry.async_get_entity_id(
                    self._entity.platform.domain,
                    self._entity.platform.platform_name,
                    unique_id,
                )
            )
            is not None
        ]
        return self._included_entity_ids

    @callback
    def async_added_to_hass(self, entity: Entity) -> None:
        """Handle when the entity is added to hass."""
        self._entity = entity
        super().async_added_to_hass(entity)

        entity_registry = er.async_get(entity.hass)

        async def _handle_entity_registry_updated(event: Event[Any]) -> None:
            """Handle registry create or update event."""
            if (
                event.data["action"] in {"create", "update"}
                and (entry := entity_registry.async_get(event.data["entity_id"]))
                and entry.unique_id in self.included_unique_ids
            ) or (
                event.data["action"] == "remove"
                and self._included_entity_ids is not None
                and event.data["entity_id"] in self._included_entity_ids
            ):
                entity.async_write_ha_state()

        entity.async_on_remove(
            entity.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                _handle_entity_registry_updated,
            )
        )


@callback
@singleton(DATA_GROUP_ENTITIES)
def get_group_entities(hass: HomeAssistant) -> dict[str, Entity]:
    """Get the group entities.

    Items are added to this dict by Group.async_added_to_hass and
    removed by Group.async_will_remove_from_hass.
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
        if (entity := group_entities.get(entity_id)) is not None and isinstance(
            entity.group, GenericGroup
        ):
            child_entities = entity.group.included_entity_ids
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
