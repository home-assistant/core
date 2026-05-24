"""Provide the functionality to group entities."""

import logging
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,  # noqa: F401
    CONF_ENTITIES,
    CONF_ICON,
    CONF_NAME,
    SERVICE_RELOAD,  # noqa: F401
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.group import (
    expand_entity_ids as _expand_entity_ids,
)
from homeassistant.helpers.group import (
    get_entity_ids as _get_entity_ids,
)
from homeassistant.helpers.group import (
    get_group_entities,
)
from homeassistant.helpers.typing import ConfigType

#
# Below we ensure the config_flow is imported so it does not need the import
# executor later.
#
# Since group is pre-imported, the loader will not get a chance to pre-import
# the config flow as there is no run time import of the group component in the
# executor.
#
from . import config_flow as config_flow_pre_import  # noqa: F401
from .const import (  # noqa: F401
    ATTR_ADD_ENTITIES,
    ATTR_ALL,
    ATTR_AUTO,
    ATTR_ENTITIES,
    ATTR_OBJECT_ID,
    ATTR_ORDER,
    ATTR_REMOVE_ENTITIES,
    CONF_ALL,
    CONF_GROUP_TYPE,
    CONF_HIDE_MEMBERS,
    CONF_IGNORE_NON_NUMERIC,
    DATA_COMPONENT,
    DOMAIN,
    GROUP_ORDER,
    PLATFORMS,
    REG_KEY,
    SERVICE_REMOVE,
    SERVICE_SET,
)
from .entity import Group  # noqa: F401
from .registry import async_setup as async_setup_registry
from .services import async_process_config, async_setup_services

_LOGGER = logging.getLogger(__name__)


def _conf_preprocess(value: Any) -> dict[str, Any]:
    """Preprocess alternative configuration formats."""
    if not isinstance(value, dict):
        return {CONF_ENTITIES: value}

    return value


GROUP_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Optional(CONF_ENTITIES): probatio.Any(cv.entity_ids, None),
            CONF_NAME: cv.string,
            CONF_ICON: cv.icon,
            CONF_ALL: cv.boolean,
        }
    )
)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {cv.match_all: probatio.All(_conf_preprocess, GROUP_SCHEMA)}
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Test if the group state is in its ON-state."""
    if REG_KEY not in hass.data:
        # Integration not setup yet, it cannot be on
        return False

    if (state := hass.states.get(entity_id)) is not None:
        return state.state in hass.data[REG_KEY].on_off_mapping

    return False


# expand_entity_ids and get_entity_ids are for backwards compatibility only
expand_entity_ids = _expand_entity_ids
get_entity_ids = _get_entity_ids


def groups_with_entity(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get all groups that contain this entity.

    Async friendly.
    """
    groups: list[str] = []

    if DOMAIN in hass.data:
        groups.extend(
            group.entity_id
            for group in hass.data[DATA_COMPONENT].entities
            if entity_id in group.tracking
        )

    groups.extend(
        group_entity_id
        for group_entity_id, entity in get_group_entities(hass).items()
        if entity.group is not None
        and entity_id in entity.group.member_entity_ids
        and group_entity_id not in groups
    )

    # Config entry groups whose platform does not (yet) register in
    # the group entities registry of the group helper.
    entity_registry = er.async_get(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        members = [
            er.async_resolve_entity_id(entity_registry, member) or member
            for member in entry.options[CONF_ENTITIES]
        ]
        if entity_id not in members:
            continue
        groups.extend(
            registry_entry.entity_id
            for registry_entry in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            )
            if registry_entry.entity_id not in groups
        )

    return groups


async def async_clean_import(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up after import from Min/Max helper."""
    old_config_entry_id = entry.options["old_config_entry_id"]
    old_config_entry = hass.config_entries.async_get_entry(old_config_entry_id)
    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, old_config_entry_id)
    old_entity_entry = entities[0] if entities else None
    if not old_config_entry or not old_entity_entry:
        # User has manually removed it before we came here
        # Skip the migration and just continue with setting up the group sensor
        _LOGGER.warning(
            "Min/Max helper has already been removed, setting up group sensor without migration"
        )
    else:
        if TYPE_CHECKING:
            assert old_entity_entry.config_entry_id
        await hass.config_entries.async_unload(old_entity_entry.config_entry_id)
        entity_reg.async_update_entity_platform(
            old_entity_entry.entity_id,
            DOMAIN,
            new_config_entry_id=entry.entry_id,
            new_unique_id=entry.entry_id,
        )
        new_options = dict(entry.options)
        new_options.pop("old_config_entry_id")
        hass.config_entries.async_update_entry(entry, options=new_options)
        await hass.config_entries.async_remove(old_entity_entry.config_entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    if "old_config_entry_id" in entry.options:
        await async_clean_import(hass, entry)
    await hass.config_entries.async_forward_entry_setups(
        entry, (entry.options["group_type"],)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, (entry.options["group_type"],)
    )


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    # Unhide the group members
    registry = er.async_get(hass)

    if not entry.options[CONF_HIDE_MEMBERS]:
        return

    for member in entry.options[CONF_ENTITIES]:
        if not (entity_id := er.async_resolve_entity_id(registry, member)):
            continue
        if (entity_entry := registry.async_get(entity_id)) is None:
            continue
        if entity_entry.hidden_by != er.RegistryEntryHider.INTEGRATION:
            continue

        registry.async_update_entity(entity_id, hidden_by=None)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up all groups found defined in the configuration."""
    await async_setup_registry(hass)

    await async_process_config(hass, config)

    async_setup_services(hass)

    return True
