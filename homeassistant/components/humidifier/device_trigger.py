"""Provides device automations for Climate."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    toggle_entity,
)
from homeassistant.components.homeassistant.triggers import (
    numeric_state as numeric_state_trigger,
)
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
    CONF_TYPE,
    PERCENTAGE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

# mypy: disallow-any-generics

HUMIDIFIER_TRIGGER_SCHEMA = vol.All(
    DEVICE_TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_TYPE): "target_humidity_changed",
            vol.Optional(CONF_BELOW): vol.Any(vol.Coerce(int)),
            vol.Optional(CONF_ABOVE): vol.Any(vol.Coerce(int)),
            vol.Optional(CONF_FOR): cv.positive_time_period_dict,
        }
    ),
    cv.has_at_least_one_key(CONF_BELOW, CONF_ABOVE),
)

TRIGGER_SCHEMA = vol.All(
    vol.Any(
        HUMIDIFIER_TRIGGER_SCHEMA,
        toggle_entity.TRIGGER_SCHEMA,
    ),
    vol.Schema({vol.Required(CONF_DOMAIN): DOMAIN}, extra=vol.ALLOW_EXTRA),
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Humidifier devices."""
    registry = entity_registry.async_get(hass)
    triggers = await toggle_entity.async_get_triggers(hass, device_id, DOMAIN)

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "target_humidity_changed",
            }
        )
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    if config[CONF_TYPE] == "target_humidity_changed":
        numeric_state_config = {
            numeric_state_trigger.CONF_PLATFORM: "numeric_state",
            numeric_state_trigger.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
            numeric_state_trigger.CONF_VALUE_TEMPLATE: "{{ state.attributes.humidity }}",
        }

        if CONF_ABOVE in config:
            numeric_state_config[CONF_ABOVE] = config[CONF_ABOVE]
        if CONF_BELOW in config:
            numeric_state_config[CONF_BELOW] = config[CONF_BELOW]
        if CONF_FOR in config:
            numeric_state_config[CONF_FOR] = config[CONF_FOR]

        numeric_state_config = (
            await numeric_state_trigger.async_validate_trigger_config(
                hass, numeric_state_config
            )
        )
        return await numeric_state_trigger.async_attach_trigger(
            hass, numeric_state_config, action, automation_info, platform_type="device"
        )

    return await toggle_entity.async_attach_trigger(
        hass, config, action, automation_info
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    if config[CONF_TYPE] == "target_humidity_changed":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(
                        CONF_ABOVE, description={"suffix": PERCENTAGE}
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_BELOW, description={"suffix": PERCENTAGE}
                    ): vol.Coerce(int),
                    vol.Optional(CONF_FOR): cv.positive_time_period_dict,
                }
            )
        }
    return await toggle_entity.async_get_trigger_capabilities(hass, config)
