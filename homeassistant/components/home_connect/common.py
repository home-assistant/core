"""Common callbacks for all Home Connect platforms."""

from collections.abc import Callable
from functools import partial
from typing import cast

from aiohomeconnect.model import EventKey

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
from .entity import HomeConnectEntity


def _handle_paired_or_connected_appliance(
    entry: HomeConnectConfigEntry,
    known_entity_unique_ids: dict[str, str],
    get_entities_for_appliance: Callable[
        [HomeConnectConfigEntry, HomeConnectApplianceData], list[HomeConnectEntity]
    ],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Handle a new paired appliance or an appliance that has been connected.

    This function is used to handle connected events also, because some appliances
    don't report any data while they are off because they disconnect themselves
    when they are turned off, so we need to check if the entities have been added
    already or it is the first time we see them when the appliance is connected.
    """
    entities: list[HomeConnectEntity] = []
    for appliance in entry.runtime_data.data.values():
        entities_to_add = [
            entity
            for entity in get_entities_for_appliance(entry, appliance)
            if entity.unique_id not in known_entity_unique_ids
        ]
        known_entity_unique_ids.update(
            {
                cast(str, entity.unique_id): appliance.info.ha_id
                for entity in entities_to_add
            }
        )
        entities.extend(entities_to_add)
    async_add_entities(entities)


def _handle_depaired_appliance(
    entry: HomeConnectConfigEntry,
    known_entity_unique_ids: dict[str, str],
) -> None:
    """Handle a removed appliance."""
    for entity_unique_id, appliance_id in known_entity_unique_ids.copy().items():
        if appliance_id not in entry.runtime_data.data:
            known_entity_unique_ids.pop(entity_unique_id, None)


def setup_home_connect_entry(
    entry: HomeConnectConfigEntry,
    get_entities_for_appliance: Callable[
        [HomeConnectConfigEntry, HomeConnectApplianceData], list[HomeConnectEntity]
    ],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the callbacks for paired and depaired appliances."""
    known_entity_unique_ids: dict[str, str] = {}

    entities: list[HomeConnectEntity] = []
    for appliance in entry.runtime_data.data.values():
        entities_to_add = get_entities_for_appliance(entry, appliance)
        known_entity_unique_ids.update(
            {
                cast(str, entity.unique_id): appliance.info.ha_id
                for entity in entities_to_add
            }
        )
        entities.extend(entities_to_add)
    async_add_entities(entities)

    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(
            partial(
                _handle_paired_or_connected_appliance,
                entry,
                known_entity_unique_ids,
                get_entities_for_appliance,
                async_add_entities,
            ),
            (
                EventKey.BSH_COMMON_APPLIANCE_PAIRED,
                EventKey.BSH_COMMON_APPLIANCE_CONNECTED,
            ),
        )
    )
    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(
            partial(_handle_depaired_appliance, entry, known_entity_unique_ids),
            (EventKey.BSH_COMMON_APPLIANCE_DEPAIRED,),
        )
    )
