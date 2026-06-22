"""Helper functions for the homee custom component."""

from collections.abc import Callable, Coroutine
from enum import IntEnum
import logging
from typing import Any

from pyHomee.model import HomeeNode

from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry

_LOGGER = logging.getLogger(__name__)


async def setup_homee_platform(
    add_platform_entities: Callable[
        [HomeeConfigEntry, AddConfigEntryEntitiesCallback, list[HomeeNode]],
        Coroutine[Any, Any, None],
    ],
    async_add_entities: AddConfigEntryEntitiesCallback,
    config_entry: HomeeConfigEntry,
) -> None:
    """Set up a homee platform."""
    await add_platform_entities(
        config_entry, async_add_entities, config_entry.runtime_data.nodes
    )

    async def add_device(node: HomeeNode, add: bool) -> None:
        """Dynamically add entities."""
        if add:
            await add_platform_entities(config_entry, async_add_entities, [node])

    config_entry.async_on_unload(
        config_entry.runtime_data.add_nodes_listener(add_device)
    )


def get_name_for_enum(att_class: type[IntEnum], att_id: int) -> str | None:
    """Return the enum item name for a given integer."""
    try:
        item = att_class(att_id)
    except ValueError:
        _LOGGER.warning("Value %s does not exist in %s", att_id, att_class.__name__)
        return None
    return item.name.lower()
