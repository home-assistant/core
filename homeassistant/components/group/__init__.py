"""Provide the functionality to group entities."""

from __future__ import annotations

import asyncio
from collections.abc import Collection
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,  # noqa: F401
    ATTR_ICON,
    ATTR_NAME,
    CONF_ENTITIES,
    CONF_ICON,
    CONF_NAME,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.group import (
    expand_entity_ids as _expand_entity_ids,
    get_entity_ids as _get_entity_ids,
)
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

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
    CONF_HIDE_MEMBERS,
    DOMAIN,
    GROUP_ORDER,
    REG_KEY,
)
from .entity import Group, async_get_component
from .registry import GroupIntegrationRegistry, async_setup as async_setup_registry

CONF_ALL = "all"


SERVICE_SET = "set"
SERVICE_REMOVE = "remove"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


def _conf_preprocess(value: Any) -> dict[str, Any]:
    """Preprocess alternative configuration formats."""
    if not isinstance(value, dict):
        return {CONF_ENTITIES: value}

    return value


GROUP_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_ENTITIES): vol.Any(cv.entity_ids, None),
            CONF_NAME: cv.string,
            CONF_ICON: cv.icon,
            CONF_ALL: cv.boolean,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.match_all: vol.All(_conf_preprocess, GROUP_SCHEMA)})},
    extra=vol.ALLOW_EXTRA,
)


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Test if the group state is in its ON-state."""
    if REG_KEY not in hass.data:
        # Integration not setup yet, it cannot be on
        return False

    if (state := hass.states.get(entity_id)) is not None:
        registry: GroupIntegrationRegistry = hass.data[REG_KEY]
        return state.state in registry.on_off_mapping

    return False


# expand_entity_ids and get_entity_ids are for backwards compatibility only
expand_entity_ids = bind_hass(_expand_entity_ids)
get_entity_ids = bind_hass(_get_entity_ids)


@bind_hass
def groups_with_entity(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get all groups that contain this entity.

    Async friendly.
    """
    if DOMAIN not in hass.data:
        return []

    return [
        group.entity_id
        for group in hass.data[DOMAIN].entities
        if entity_id in group.tracking
    ]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    await hass.config_entries.async_forward_entry_setups(
        entry, (entry.options["group_type"],)
    )
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


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
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = EntityComponent[Group](_LOGGER, DOMAIN, hass)

    component: EntityComponent[Group] = hass.data[DOMAIN]

    await async_setup_registry(hass)

    await _async_process_config(hass, config)

    async def reload_service_handler(service: ServiceCall) -> None:
        """Group reload handler.

        - Remove group.group entities not created by service calls and set them up again
        - Reload xxx.group platforms
        """
        if (conf := await component.async_prepare_reload(skip_reset=True)) is None:
            return

        # Simplified + modified version of EntityPlatform.async_reset:
        # - group.group never retries setup
        # - group.group never polls
        # - We don't need to reset EntityPlatform._setup_complete
        # - Only remove entities which were not created by service calls
        tasks = [
            entity.async_remove()
            for entity in component.entities
            if entity.entity_id.startswith("group.") and not entity.created_by_service
        ]

        if tasks:
            await asyncio.gather(*tasks)

        component.config = None

        await _async_process_config(hass, conf)

        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    service_lock = asyncio.Lock()

    async def locked_service_handler(service: ServiceCall) -> None:
        """Handle a service with an async lock."""
        async with service_lock:
            await groups_service_handler(service)

    async def groups_service_handler(service: ServiceCall) -> None:
        """Handle dynamic group service functions."""
        object_id = service.data[ATTR_OBJECT_ID]
        entity_id = f"{DOMAIN}.{object_id}"
        group = component.get_entity(entity_id)

        # new group
        if service.service == SERVICE_SET and group is None:
            entity_ids = (
                service.data.get(ATTR_ENTITIES)
                or service.data.get(ATTR_ADD_ENTITIES)
                or None
            )

            await Group.async_create_group(
                hass,
                service.data.get(ATTR_NAME, object_id),
                created_by_service=True,
                entity_ids=entity_ids,
                icon=service.data.get(ATTR_ICON),
                mode=service.data.get(ATTR_ALL),
                object_id=object_id,
                order=None,
            )
            return

        if group is None:
            _LOGGER.warning("%s:Group '%s' doesn't exist!", service.service, object_id)
            return

        # update group
        if service.service == SERVICE_SET:
            need_update = False

            if ATTR_ADD_ENTITIES in service.data:
                delta = service.data[ATTR_ADD_ENTITIES]
                entity_ids = set(group.tracking) | set(delta)
                group.async_update_tracked_entity_ids(entity_ids)

            if ATTR_REMOVE_ENTITIES in service.data:
                delta = service.data[ATTR_REMOVE_ENTITIES]
                entity_ids = set(group.tracking) - set(delta)
                group.async_update_tracked_entity_ids(entity_ids)

            if ATTR_ENTITIES in service.data:
                entity_ids = service.data[ATTR_ENTITIES]
                group.async_update_tracked_entity_ids(entity_ids)

            if ATTR_NAME in service.data:
                group.set_name(service.data[ATTR_NAME])
                need_update = True

            if ATTR_ICON in service.data:
                group.set_icon(service.data[ATTR_ICON])
                need_update = True

            if ATTR_ALL in service.data:
                group.mode = all if service.data[ATTR_ALL] else any
                need_update = True

            if need_update:
                group.async_write_ha_state()

            return

        # remove group
        if service.service == SERVICE_REMOVE:
            await component.async_remove_entity(entity_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET,
        locked_service_handler,
        schema=vol.All(
            vol.Schema(
                {
                    vol.Required(ATTR_OBJECT_ID): cv.slug,
                    vol.Optional(ATTR_NAME): cv.string,
                    vol.Optional(ATTR_ICON): cv.string,
                    vol.Optional(ATTR_ALL): cv.boolean,
                    vol.Exclusive(ATTR_ENTITIES, "entities"): cv.entity_ids,
                    vol.Exclusive(ATTR_ADD_ENTITIES, "entities"): cv.entity_ids,
                    vol.Exclusive(ATTR_REMOVE_ENTITIES, "entities"): cv.entity_ids,
                }
            )
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE,
        groups_service_handler,
        schema=vol.Schema({vol.Required(ATTR_OBJECT_ID): cv.slug}),
    )

    return True


async def _async_process_config(hass: HomeAssistant, config: ConfigType) -> None:
    """Process group configuration."""
    hass.data.setdefault(GROUP_ORDER, 0)

    entities = []
    domain_config: dict[str, dict[str, Any]] = config.get(DOMAIN, {})

    for object_id, conf in domain_config.items():
        name: str = conf.get(CONF_NAME, object_id)
        entity_ids: Collection[str] = conf.get(CONF_ENTITIES) or []
        icon: str | None = conf.get(CONF_ICON)
        mode = bool(conf.get(CONF_ALL))
        order: int = hass.data[GROUP_ORDER]

        # We keep track of the order when we are creating the tasks
        # in the same way that async_create_group does to make
        # sure we use the same ordering system.  This overcomes
        # the problem with concurrently creating the groups
        entities.append(
            Group.async_create_group_entity(
                hass,
                name,
                created_by_service=False,
                entity_ids=entity_ids,
                icon=icon,
                object_id=object_id,
                mode=mode,
                order=order,
            )
        )

        # Keep track of the group order without iterating
        # every state in the state machine every time
        # we setup a new group
        hass.data[GROUP_ORDER] += 1

    # If called before the platform async_setup is called (test cases)
    await async_get_component(hass).async_add_entities(entities)
