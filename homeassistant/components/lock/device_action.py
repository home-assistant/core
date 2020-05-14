"""Provides device automations for Lock."""
from typing import List, Optional

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, SUPPORT_OPEN

ACTION_TYPES = {"lock", "unlock", "open"}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions for Lock devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        # Add actions for each entity that belongs to this integration
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "lock",
            }
        )
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "unlock",
            }
        )

        state = hass.states.get(entry.entity_id)
        if state:
            features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            if features & (SUPPORT_OPEN):
                actions.append(
                    {
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "open",
                    }
                )

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Optional[Context]
) -> None:
    """Execute a device action."""
    config = ACTION_SCHEMA(config)

    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}

    if config[CONF_TYPE] == "lock":
        service = SERVICE_LOCK
    elif config[CONF_TYPE] == "unlock":
        service = SERVICE_UNLOCK
    elif config[CONF_TYPE] == "open":
        service = SERVICE_OPEN

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )
