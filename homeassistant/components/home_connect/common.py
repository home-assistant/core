"""Common callbacks for all Home Connect platforms."""

from collections import defaultdict
from collections.abc import Callable
from functools import partial
from typing import cast

from aiohomeconnect.model import EventKey

from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
from .entity import HomeConnectEntity, HomeConnectOptionEntity


def _create_option_entities(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
    known_entity_unique_ids: dict[str, str],
    get_option_entities_for_appliance: Callable[
        [HomeConnectConfigEntry, HomeConnectApplianceData],
        list[HomeConnectOptionEntity],
    ],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the required option entities for the appliances."""
    option_entities_to_add = [
        entity
        for entity in get_option_entities_for_appliance(entry, appliance)
        if entity.unique_id not in known_entity_unique_ids
    ]
    known_entity_unique_ids.update(
        {
            cast(str, entity.unique_id): appliance.info.ha_id
            for entity in option_entities_to_add
        }
    )
    async_add_entities(option_entities_to_add)


def _handle_paired_or_connected_appliance(
    entry: HomeConnectConfigEntry,
    known_entity_unique_ids: dict[str, str],
    get_entities_for_appliance: Callable[
        [HomeConnectConfigEntry, HomeConnectApplianceData], list[HomeConnectEntity]
    ],
    get_option_entities_for_appliance: Callable[
        [HomeConnectConfigEntry, HomeConnectApplianceData],
        list[HomeConnectOptionEntity],
    ]
    | None,
    changed_options_listener_remove_callbacks: dict[str, list[Callable[[], None]]],
    async_add_entities: AddConfigEntryEntitiesCallback,
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
        if get_option_entities_for_appliance:
            entities_to_add.extend(
                entity
                for entity in get_option_entities_for_appliance(entry, appliance)
                if entity.unique_id not in known_entity_unique_ids
            )
            for event_key in (
                EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
                EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
            ):
                changed_options_listener_remove_callback = (
                    entry.runtime_data.async_add_listener(
                        partial(
                            _create_option_entities,
                            entry,
                            appliance,
                            known_entity_unique_ids,
                            get_option_entities_for_appliance,
                            async_add_entities,
                        ),
                        (appliance.info.ha_id, event_key),
                    )
                )
                entry.async_on_unload(changed_options_listener_remove_callback)
                changed_options_listener_remove_callbacks[appliance.info.ha_id].append(
                    changed_options_listener_remove_callback
                )
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
    changed_options_listener_remove_callbacks: dict[str, list[Callable[[], None]]],
) -> None:
    """Handle a removed appliance."""
    for entity_unique_id, appliance_id in known_entity_unique_ids.copy().items():
        if appliance_id not in entry.runtime_data.data:
            known_entity_unique_ids.pop(entity_unique_id, None)
            if appliance_id in changed_options_listener_remove_callbacks:
                for listener in changed_options_listener_remove_callbacks.pop(
                    appliance_id
                ):
                    listener()


def setup_home_connect_entry(
    entry: HomeConnectConfigEntry,
    get_entities_for_appliance: Callable[
        [HomeConnectConfigEntry, HomeConnectApplianceData], list[HomeConnectEntity]
    ],
    async_add_entities: AddConfigEntryEntitiesCallback,
    get_option_entities_for_appliance: Callable[
        [HomeConnectConfigEntry, HomeConnectApplianceData],
        list[HomeConnectOptionEntity],
    ]
    | None = None,
) -> None:
    """Set up the callbacks for paired and depaired appliances."""
    known_entity_unique_ids: dict[str, str] = {}
    changed_options_listener_remove_callbacks: dict[str, list[Callable[[], None]]] = (
        defaultdict(list)
    )

    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(
            partial(
                _handle_paired_or_connected_appliance,
                entry,
                known_entity_unique_ids,
                get_entities_for_appliance,
                get_option_entities_for_appliance,
                changed_options_listener_remove_callbacks,
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
            partial(
                _handle_depaired_appliance,
                entry,
                known_entity_unique_ids,
                changed_options_listener_remove_callbacks,
            ),
            (EventKey.BSH_COMMON_APPLIANCE_DEPAIRED,),
        )
    )
