"""Support for recorder services."""
from __future__ import annotations

from datetime import timedelta
from typing import cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.helpers.service import (
    async_extract_entity_ids,
    async_register_admin_service,
)
import homeassistant.util.dt as dt_util

from .const import ATTR_APPLY_FILTER, ATTR_KEEP_DAYS, ATTR_REPACK, DOMAIN
from .core import Recorder
from .tasks import PurgeEntitiesTask, PurgeTask

SERVICE_PURGE = "purge"
SERVICE_PURGE_ENTITIES = "purge_entities"
SERVICE_ENABLE = "enable"
SERVICE_DISABLE = "disable"

SERVICE_PURGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_KEEP_DAYS): cv.positive_int,
        vol.Optional(ATTR_REPACK, default=False): cv.boolean,
        vol.Optional(ATTR_APPLY_FILTER, default=False): cv.boolean,
    }
)

ATTR_DOMAINS = "domains"
ATTR_ENTITY_GLOBS = "entity_globs"

SERVICE_PURGE_ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DOMAINS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ENTITY_GLOBS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(ATTR_KEEP_DAYS, default=0): cv.positive_int,
    }
).extend(cv.ENTITY_SERVICE_FIELDS)

SERVICE_ENABLE_SCHEMA = vol.Schema({})
SERVICE_DISABLE_SCHEMA = vol.Schema({})


@callback
def _async_register_purge_service(hass: HomeAssistant, instance: Recorder) -> None:
    async def async_handle_purge_service(service: ServiceCall) -> None:
        """Handle calls to the purge service."""
        kwargs = service.data
        keep_days = kwargs.get(ATTR_KEEP_DAYS, instance.keep_days)
        repack = cast(bool, kwargs[ATTR_REPACK])
        apply_filter = cast(bool, kwargs[ATTR_APPLY_FILTER])
        purge_before = dt_util.utcnow() - timedelta(days=keep_days)
        instance.queue_task(PurgeTask(purge_before, repack, apply_filter))

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_PURGE,
        async_handle_purge_service,
        schema=SERVICE_PURGE_SCHEMA,
    )


@callback
def _async_register_purge_entities_service(
    hass: HomeAssistant, instance: Recorder
) -> None:
    async def async_handle_purge_entities_service(service: ServiceCall) -> None:
        """Handle calls to the purge entities service."""
        entity_ids = await async_extract_entity_ids(hass, service)
        domains = service.data.get(ATTR_DOMAINS, [])
        keep_days = service.data.get(ATTR_KEEP_DAYS, 0)
        entity_globs = service.data.get(ATTR_ENTITY_GLOBS, [])
        entity_filter = generate_filter(domains, list(entity_ids), [], [], entity_globs)
        purge_before = dt_util.utcnow() - timedelta(days=keep_days)
        instance.queue_task(PurgeEntitiesTask(entity_filter, purge_before))

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_PURGE_ENTITIES,
        async_handle_purge_entities_service,
        schema=SERVICE_PURGE_ENTITIES_SCHEMA,
    )


@callback
def _async_register_enable_service(hass: HomeAssistant, instance: Recorder) -> None:
    async def async_handle_enable_service(service: ServiceCall) -> None:
        instance.set_enable(True)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ENABLE,
        async_handle_enable_service,
        schema=SERVICE_ENABLE_SCHEMA,
    )


@callback
def _async_register_disable_service(hass: HomeAssistant, instance: Recorder) -> None:
    async def async_handle_disable_service(service: ServiceCall) -> None:
        instance.set_enable(False)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_DISABLE,
        async_handle_disable_service,
        schema=SERVICE_DISABLE_SCHEMA,
    )


@callback
def async_register_services(hass: HomeAssistant, instance: Recorder) -> None:
    """Register recorder services."""
    _async_register_purge_service(hass, instance)
    _async_register_purge_entities_service(hass, instance)
    _async_register_enable_service(hass, instance)
    _async_register_disable_service(hass, instance)
