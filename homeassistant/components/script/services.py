"""Services for the script integration."""

import asyncio

import probatio

from homeassistant.const import (
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.async_ import create_eager_task

from .const import ATTR_VARIABLES, DOMAIN
from .entity import BaseScriptEntity
from .helpers import async_get_blueprints
from .util import async_process_config

SCRIPT_TURN_ONOFF_SCHEMA = make_entity_service_schema(
    {probatio.Optional(ATTR_VARIABLES): {str: cv.match_all}}
)
RELOAD_SERVICE_SCHEMA = probatio.Schema({})


async def _reload_service(service: ServiceCall) -> None:
    """Call a service to reload scripts."""
    component: EntityComponent[BaseScriptEntity] = service.hass.data[DOMAIN]
    await async_get_blueprints(service.hass).async_reset_cache()
    conf = await component.async_prepare_reload(skip_reset=True)
    await async_process_config(service.hass, conf, component)


async def _turn_on_service(service: ServiceCall) -> None:
    """Call a service to turn script on."""
    component: EntityComponent[BaseScriptEntity] = service.hass.data[DOMAIN]
    variables = service.data.get(ATTR_VARIABLES)
    script_entities = await component.async_extract_from_service(service)
    for script_entity in script_entities:
        await script_entity.async_turn_on(
            variables=variables, context=service.context, wait=False
        )


async def _turn_off_service(service: ServiceCall) -> None:
    """Cancel a script."""
    component: EntityComponent[BaseScriptEntity] = service.hass.data[DOMAIN]
    # Stopping a script is ok to be done in parallel
    script_entities = await component.async_extract_from_service(service)

    if not script_entities:
        return

    for script_entity in script_entities:
        script_entity.async_set_context(service.context)

    await asyncio.wait(
        [
            create_eager_task(script_entity.async_turn_off())
            for script_entity in script_entities
        ]
    )


async def _toggle_service(service: ServiceCall) -> None:
    """Toggle a script."""
    component: EntityComponent[BaseScriptEntity] = service.hass.data[DOMAIN]
    script_entities = await component.async_extract_from_service(service)
    for script_entity in script_entities:
        await script_entity.async_toggle(context=service.context, wait=False)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the script services."""
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, _reload_service, schema=RELOAD_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, _turn_on_service, schema=SCRIPT_TURN_ONOFF_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_OFF, _turn_off_service, schema=SCRIPT_TURN_ONOFF_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, _toggle_service, schema=SCRIPT_TURN_ONOFF_SCHEMA
    )
