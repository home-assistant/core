"""Services for the automation integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    ReloadServiceHelper,
    async_register_admin_service,
)

from .const import (
    DATA_COMPONENT,
    DEFAULT_STOP_ACTIONS,
    DOMAIN,
    EVENT_AUTOMATION_RELOADED,
    AutomationService,
    AutomationServiceArgument,
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
        {
            **service_call.data[AutomationServiceArgument.VARIABLES],
            "trigger": {"platform": None},
        },
        skip_condition=service_call.data[AutomationServiceArgument.SKIP_CONDITION],
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
        AutomationService.TRIGGER,
        {
            probatio.Optional(AutomationServiceArgument.VARIABLES, default={}): dict,
            probatio.Optional(
                AutomationServiceArgument.SKIP_CONDITION, default=True
            ): bool,
        },
        _trigger_service_handler,
    )
    component.async_register_entity_service(
        AutomationService.TOGGLE, None, "async_toggle"
    )
    component.async_register_entity_service(
        AutomationService.TURN_ON, None, "async_turn_on"
    )
    component.async_register_entity_service(
        AutomationService.TURN_OFF,
        {
            probatio.Optional(
                AutomationServiceArgument.STOP_ACTIONS, default=DEFAULT_STOP_ACTIONS
            ): cv.boolean
        },
        "async_turn_off",
    )

    reload_helper = ReloadServiceHelper(_async_reload_service_handler, _reload_targets)
    async_register_admin_service(
        hass,
        DOMAIN,
        AutomationService.RELOAD,
        reload_helper.execute_service,
        schema=probatio.Schema({probatio.Optional(CONF_ID): str}),
    )
