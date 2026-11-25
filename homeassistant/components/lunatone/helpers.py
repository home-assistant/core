"""Shared helpers for Lunatone entities."""

from collections.abc import Callable, Mapping

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


def format_device_identifier(
    config_entry_unique_id: str, line_id: int | None = None
) -> str:
    """Return the unique ID of a device."""
    suffix = f"-line{line_id}" if line_id is not None else ""
    return f"{config_entry_unique_id}{suffix}"


def add_entities_from_builder(
    entity_builder: Mapping[str, Callable[[], Entity]],
    known_entities: set[str],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add newly discovered entities and track their unique IDs."""
    current_entities = entity_builder.keys()
    new_entities = current_entities - known_entities
    stale_entities = known_entities - current_entities

    if new_entities:
        async_add_entities(
            [entity_builder[entity_unique_id]() for entity_unique_id in new_entities]
        )
        known_entities.update(new_entities)
    known_entities.difference_update(stale_entities)
