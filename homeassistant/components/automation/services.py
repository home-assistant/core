"""Services for the automation integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.const import (
    CONF_ID,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    ReloadServiceHelper,
    async_register_admin_service,
)

from .const import (
    ATTR_VARIABLES,
    CONF_SKIP_CONDITION,
    CONF_STOP_ACTIONS,
    DATA_COMPONENT,
    DEFAULT_STOP_ACTIONS,
    DOMAIN,
    EVENT_AUTOMATION_RELOADED,
    SERVICE_TRIGGER,
)
from .helpers import async_get_blueprints
from .util import async_process_config, async_process_single_config

if TYPE_CHECKING:
    from .entity import BaseAutomationEntity


async def _trigger_service_handler(
    entity: BaseAutomationEntity, service_call: ServiceCall
) -> None:
    """Handle forced automation trigger, e.g. from frontend."""
    await entity.async_trigger(
        {**service_call.data[ATTR_VARIABLES], "trigger": {"platform": None}},
        skip_condition=service_call.data[CONF_SKIP_CONDITION],
        context=service_call.context,
    )


async def _async_reload_service_handler(service_call: ServiceCall) -> None:
    """Remove all automations and load new ones from config."""
    hass = service_call.hass
    component = hass.data[DATA_COMPONENT]
    await async_get_blueprints(hass).async_reset_cache()
    conf = await component.async_prepare_reload(skip_reset=True)
    if automation_id := service_call.data.get(CONF_ID):
        await async_process_single_config(hass, conf, component, automation_id)
    else:
        await async_process_config(hass, conf, component)
    hass.bus.async_fire(EVENT_AUTOMATION_RELOADED, context=service_call.context)


def _reload_targets(service_call: ServiceCall) -> set[str | None]:
    if automation_id := service_call.data.get(CONF_ID):
        return {automation_id}
    return {
        automation.unique_id
        for automation in service_call.hass.data[DATA_COMPONENT].entities
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the automation integration."""
    component = hass.data[DATA_COMPONENT]
    component.async_register_entity_service(
        SERVICE_TRIGGER,
        {
            probatio.Optional(ATTR_VARIABLES, default={}): dict,
            probatio.Optional(CONF_SKIP_CONDITION, default=True): bool,
        },
        _trigger_service_handler,
    )
    component.async_register_entity_service(SERVICE_TOGGLE, None, "async_toggle")
    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        {
            probatio.Optional(
                CONF_STOP_ACTIONS, default=DEFAULT_STOP_ACTIONS
            ): cv.boolean
        },
        "async_turn_off",
    )

    reload_helper = ReloadServiceHelper(_async_reload_service_handler, _reload_targets)
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_helper.execute_service,
        schema=probatio.Schema({probatio.Optional(CONF_ID): str}),
    )
