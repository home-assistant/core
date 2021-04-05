"""Functions used to migrate unique IDs for Z-Wave JS entities."""
from __future__ import annotations

import logging

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.core import callback
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .helpers import get_unique_id

_LOGGER = logging.getLogger(__name__)


@callback
def async_migrate_entity(
    ent_reg: EntityRegistry, platform: str, old_unique_id: str, new_unique_id: str
) -> None:
    """Check if entity with old unique ID exists, and if so migrate it to new ID."""
    if entity_id := ent_reg.async_get_entity_id(platform, DOMAIN, old_unique_id):
        _LOGGER.debug(
            "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
            entity_id,
            old_unique_id,
            new_unique_id,
        )
        try:
            ent_reg.async_update_entity(
                entity_id,
                new_unique_id=new_unique_id,
            )
        except ValueError:
            _LOGGER.debug(
                (
                    "Entity %s can't be migrated because the unique ID is taken; "
                    "Cleaning it up since it is likely no longer valid"
                ),
                entity_id,
            )
            ent_reg.async_remove(entity_id)


@callback
def async_migrate_discovered_value(
    ent_reg: EntityRegistry, client: ZwaveClient, disc_info: ZwaveDiscoveryInfo
) -> None:
    """Migrate unique ID for entity/entities tied to discovered value."""
    new_unique_id = get_unique_id(
        client.driver.controller.home_id,
        disc_info.primary_value.value_id,
    )

    # 2021.2.*, 2021.3.0b0, and 2021.3.0 formats
    for value_id in get_old_value_ids(disc_info.primary_value):
        old_unique_id = get_unique_id(
            client.driver.controller.home_id,
            value_id,
        )
        # Most entities have the same ID format, but notification binary sensors
        # have a state key in their ID so we need to handle them differently
        if (
            disc_info.platform == "binary_sensor"
            and disc_info.platform_hint == "notification"
        ):
            for state_key in disc_info.primary_value.metadata.states:
                # ignore idle key (0)
                if state_key == "0":
                    continue

                async_migrate_entity(
                    ent_reg,
                    disc_info.platform,
                    f"{old_unique_id}.{state_key}",
                    f"{new_unique_id}.{state_key}",
                )

            # Once we've iterated through all state keys, we can move on to the
            # next item
            continue

        async_migrate_entity(ent_reg, disc_info.platform, old_unique_id, new_unique_id)


@callback
def get_old_value_ids(value: ZwaveValue) -> list[str]:
    """Get old value IDs so we can migrate entity unique ID."""
    value_ids = []

    # Pre 2021.3.0 value ID
    command_class = value.command_class
    endpoint = value.endpoint or "00"
    property_ = value.property_
    property_key_name = value.property_key_name or "00"
    value_ids.append(
        f"{value.node.node_id}.{value.node.node_id}-{command_class}-{endpoint}-"
        f"{property_}-{property_key_name}"
    )

    endpoint = "00" if value.endpoint is None else value.endpoint
    property_key = "00" if value.property_key is None else value.property_key
    property_key_name = value.property_key_name or "00"

    value_id = (
        f"{value.node.node_id}-{command_class}-{endpoint}-"
        f"{property_}-{property_key}-{property_key_name}"
    )
    # 2021.3.0b0 and 2021.3.0 value IDs
    value_ids.extend([f"{value.node.node_id}.{value_id}", value_id])

    return value_ids
