"""Provides device automations for Device tracker."""
from typing import List, Optional

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, SERVICE_SEE
from .const import ATTR_LOCATION_NAME, ATTR_DEV_ID

ACTION_TYPES = {"set_home", "set_not_home"}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions for Device tracker devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "set_home",
            }
        )
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "set_not_home",
            }
        )

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Optional[Context]
) -> None:
    """Execute a device action."""
    config = ACTION_SCHEMA(config)

    entity_id = config[CONF_ENTITY_ID]
    service_data = {ATTR_ENTITY_ID: entity_id}

    if config[CONF_TYPE] == "set_home":
        service_data[ATTR_LOCATION_NAME] = STATE_HOME
        service_data[ATTR_DEV_ID] = entity_id[entity_id.find(".") + 1 :]
    elif config[CONF_TYPE] == "set_not_home":
        service_data[ATTR_LOCATION_NAME] = STATE_NOT_HOME
        service_data[ATTR_DEV_ID] = entity_id[entity_id.find(".") + 1 :]

    await hass.services.async_call(
        DOMAIN, SERVICE_SEE, service_data, blocking=True, context=context
    )
