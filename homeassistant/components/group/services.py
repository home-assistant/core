"""Services for the group integration."""

import asyncio
from collections.abc import Collection
from functools import partial
import logging
from typing import Any

import probatio

from homeassistant.const import (
    ATTR_ICON,
    ATTR_NAME,
    CONF_ENTITIES,
    CONF_ICON,
    CONF_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ADD_ENTITIES,
    ATTR_ALL,
    ATTR_ENTITIES,
    ATTR_OBJECT_ID,
    ATTR_REMOVE_ENTITIES,
    CONF_ALL,
    DOMAIN,
    GROUP_ORDER,
    PLATFORMS,
    SERVICE_REMOVE,
    SERVICE_SET,
)
from .entity import Group, async_get_component

_LOGGER = logging.getLogger(__name__)


async def async_process_config(hass: HomeAssistant, config: ConfigType) -> None:
    """Process group configuration."""
    hass.data.setdefault(GROUP_ORDER, 0)

    entities = []
    domain_config: dict[str, dict[str, Any]] = config.get(DOMAIN, {})

    for object_id, conf in domain_config.items():
        name: str = conf.get(CONF_NAME, object_id)
        entity_ids: Collection[str] = conf.get(CONF_ENTITIES) or []
        icon: str | None = conf.get(CONF_ICON)
        mode = bool(conf.get(CONF_ALL))
        order = hass.data[GROUP_ORDER]

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


async def _async_reload_service(service: ServiceCall) -> None:
    """Group reload handler.

    - Remove group.group entities not created by service calls and set them up again
    - Reload xxx.group platforms
    """
    hass = service.hass
    component = async_get_component(hass)
    conf = await component.async_prepare_reload(skip_reset=True)

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

    await async_process_config(hass, conf)

    await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)


async def _async_groups_service(service: ServiceCall) -> None:
    """Handle dynamic group service functions."""
    hass = service.hass
    component = async_get_component(hass)
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
            context=service.context,
        )
        return

    if group is None:
        _LOGGER.warning("%s:Group '%s' doesn't exist!", service.service, object_id)
        return

    group.async_set_context(service.context)

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


async def _async_locked_groups_service(
    service_lock: asyncio.Lock, service: ServiceCall
) -> None:
    """Handle a service with an async lock."""
    async with service_lock:
        await _async_groups_service(service)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the group services."""
    service_lock = asyncio.Lock()

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, _async_reload_service, schema=probatio.Schema({})
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET,
        partial(_async_locked_groups_service, service_lock),
        schema=probatio.All(
            probatio.Schema(
                {
                    probatio.Required(ATTR_OBJECT_ID): cv.slug,
                    probatio.Optional(ATTR_NAME): cv.string,
                    probatio.Optional(ATTR_ICON): cv.string,
                    probatio.Optional(ATTR_ALL): cv.boolean,
                    probatio.Exclusive(ATTR_ENTITIES, "entities"): cv.entity_ids,
                    probatio.Exclusive(ATTR_ADD_ENTITIES, "entities"): cv.entity_ids,
                    probatio.Exclusive(ATTR_REMOVE_ENTITIES, "entities"): cv.entity_ids,
                }
            )
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE,
        _async_groups_service,
        schema=probatio.Schema({probatio.Required(ATTR_OBJECT_ID): cv.slug}),
    )
