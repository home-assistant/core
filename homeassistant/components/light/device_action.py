"""Provides device actions for lights."""
from typing import List

import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.components.light import (
    ATTR_FLASH,
    FLASH_SHORT,
    SUPPORT_FLASH,
    VALID_BRIGHTNESS_PCT,
    VALID_FLASH,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_DOMAIN,
    CONF_TYPE,
    SERVICE_TURN_ON,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS_STEP_PCT, DOMAIN, SUPPORT_BRIGHTNESS

TYPE_BRIGHTNESS_INCREASE = "brightness_increase"
TYPE_BRIGHTNESS_DECREASE = "brightness_decrease"
TYPE_FLASH = "flash"

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_TYPE): vol.In(
            toggle_entity.DEVICE_ACTION_TYPES
            + [TYPE_BRIGHTNESS_INCREASE, TYPE_BRIGHTNESS_DECREASE, TYPE_FLASH]
        ),
        vol.Optional(ATTR_BRIGHTNESS_PCT): VALID_BRIGHTNESS_PCT,
        vol.Optional(ATTR_FLASH): VALID_FLASH,
    }
)


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context,
) -> None:
    """Change state based on configuration."""
    if (
        config[CONF_TYPE] in toggle_entity.DEVICE_ACTION_TYPES
        and config[CONF_TYPE] != toggle_entity.CONF_TURN_ON
    ):
        await toggle_entity.async_call_action_from_config(
            hass, config, variables, context, DOMAIN
        )
        return

    data = {ATTR_ENTITY_ID: config[ATTR_ENTITY_ID]}

    if config[CONF_TYPE] == TYPE_BRIGHTNESS_INCREASE:
        data[ATTR_BRIGHTNESS_STEP_PCT] = 10
    elif config[CONF_TYPE] == TYPE_BRIGHTNESS_DECREASE:
        data[ATTR_BRIGHTNESS_STEP_PCT] = -10
    elif ATTR_BRIGHTNESS_PCT in config:
        data[ATTR_BRIGHTNESS_PCT] = config[ATTR_BRIGHTNESS_PCT]

    if config[CONF_TYPE] == TYPE_FLASH:
        if ATTR_FLASH in config:
            data[ATTR_FLASH] = config[ATTR_FLASH]
        else:
            data[ATTR_FLASH] = FLASH_SHORT

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=context
    )


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions."""
    actions = await toggle_entity.async_get_actions(hass, device_id, DOMAIN)

    registry = await entity_registry.async_get_registry(hass)

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        state = hass.states.get(entry.entity_id)

        if state:
            supported_features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        else:
            supported_features = entry.supported_features

        if supported_features & SUPPORT_BRIGHTNESS:
            actions.extend(
                (
                    {
                        CONF_TYPE: TYPE_BRIGHTNESS_INCREASE,
                        "device_id": device_id,
                        "entity_id": entry.entity_id,
                        "domain": DOMAIN,
                    },
                    {
                        CONF_TYPE: TYPE_BRIGHTNESS_DECREASE,
                        "device_id": device_id,
                        "entity_id": entry.entity_id,
                        "domain": DOMAIN,
                    },
                )
            )

        if supported_features & SUPPORT_FLASH:
            actions.extend(
                (
                    {
                        CONF_TYPE: TYPE_FLASH,
                        "device_id": device_id,
                        "entity_id": entry.entity_id,
                        "domain": DOMAIN,
                    },
                )
            )

    return actions


async def async_get_action_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List action capabilities."""
    if config[CONF_TYPE] != toggle_entity.CONF_TURN_ON:
        return {}

    registry = await entity_registry.async_get_registry(hass)
    entry = registry.async_get(config[ATTR_ENTITY_ID])
    state = hass.states.get(config[ATTR_ENTITY_ID])

    supported_features = 0

    if state:
        supported_features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
    elif entry:
        supported_features = entry.supported_features

    extra_fields = {}

    if supported_features & SUPPORT_BRIGHTNESS:
        extra_fields[vol.Optional(ATTR_BRIGHTNESS_PCT)] = VALID_BRIGHTNESS_PCT

    if supported_features & SUPPORT_FLASH:
        extra_fields[vol.Optional(ATTR_FLASH)] = VALID_FLASH

    return {"extra_fields": vol.Schema(extra_fields)} if extra_fields else {}
