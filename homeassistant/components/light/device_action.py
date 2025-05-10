"""Provides device actions for lights."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import (
    async_get_entity_registry_entry_or_raise,
    async_validate_entity_schema,
    toggle_entity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    SERVICE_TURN_ON,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity import get_supported_features
from homeassistant.helpers.typing import ConfigType, TemplateVarsType, VolDictType

from . import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_BRIGHTNESS_STEP_PCT,
    ATTR_FLASH,
    FLASH_SHORT,
    VALID_BRIGHTNESS_PCT,
    VALID_BRIGHTNESS_STEP_PCT,
    VALID_FLASH,
    brightness_supported,
    get_supported_color_modes,
)
from .const import DOMAIN, LightEntityFeature

# mypy: disallow-any-generics

TYPE_BRIGHTNESS_INCREASE = "brightness_increase"
TYPE_BRIGHTNESS_DECREASE = "brightness_decrease"
TYPE_FLASH = "flash"

_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_TYPE): vol.In(
            [
                *toggle_entity.DEVICE_ACTION_TYPES,
                TYPE_BRIGHTNESS_INCREASE,
                TYPE_BRIGHTNESS_DECREASE,
                TYPE_FLASH,
            ]
        ),
        vol.Optional(ATTR_BRIGHTNESS_PCT): VALID_BRIGHTNESS_PCT,
        vol.Optional(ATTR_BRIGHTNESS_STEP_PCT): VALID_BRIGHTNESS_STEP_PCT,
        vol.Optional(ATTR_FLASH): VALID_FLASH,
    }
)


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    return async_validate_entity_schema(hass, config, _ACTION_SCHEMA)


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
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
        data[ATTR_BRIGHTNESS_STEP_PCT] = config.get(ATTR_BRIGHTNESS_STEP_PCT, 10)
    elif config[CONF_TYPE] == TYPE_BRIGHTNESS_DECREASE:
        data[ATTR_BRIGHTNESS_STEP_PCT] = -config.get(ATTR_BRIGHTNESS_STEP_PCT, 10)
    elif ATTR_BRIGHTNESS_PCT in config:
        data[ATTR_BRIGHTNESS_PCT] = config[ATTR_BRIGHTNESS_PCT]

    if config[CONF_TYPE] == TYPE_FLASH:
        data[ATTR_FLASH] = config.get(ATTR_FLASH, FLASH_SHORT)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=context
    )


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions."""
    actions = await toggle_entity.async_get_actions(hass, device_id, DOMAIN)

    entity_registry = er.async_get(hass)

    for entry in er.async_entries_for_device(entity_registry, device_id):
        if entry.domain != DOMAIN:
            continue

        supported_color_modes = get_supported_color_modes(hass, entry.entity_id)
        supported_features = get_supported_features(hass, entry.entity_id)

        base_action = {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.id,
        }

        if brightness_supported(supported_color_modes):
            actions.extend(
                (
                    {**base_action, CONF_TYPE: TYPE_BRIGHTNESS_INCREASE},
                    {**base_action, CONF_TYPE: TYPE_BRIGHTNESS_DECREASE},
                )
            )

        if supported_features & LightEntityFeature.FLASH:
            actions.append({**base_action, CONF_TYPE: TYPE_FLASH})

    return actions


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    try:
        entry = async_get_entity_registry_entry_or_raise(hass, config[CONF_ENTITY_ID])
        supported_color_modes = get_supported_color_modes(hass, entry.entity_id)
        supported_features = get_supported_features(hass, entry.entity_id)
    except HomeAssistantError:
        supported_color_modes = None
        supported_features = 0

    extra_fields: VolDictType = {}

    if config[CONF_TYPE] == toggle_entity.CONF_TURN_ON:
        if brightness_supported(supported_color_modes):
            extra_fields[vol.Optional(ATTR_BRIGHTNESS_PCT)] = VALID_BRIGHTNESS_PCT

        if supported_features & LightEntityFeature.FLASH:
            extra_fields[vol.Optional(ATTR_FLASH)] = VALID_FLASH

        return {"extra_fields": vol.Schema(extra_fields)} if extra_fields else {}

    if config[CONF_TYPE] in (TYPE_BRIGHTNESS_INCREASE, TYPE_BRIGHTNESS_DECREASE):
        extra_fields: VolDictType = {}
        if brightness_supported(supported_color_modes):
            extra_fields[vol.Optional(ATTR_BRIGHTNESS_STEP_PCT)] = (
                VALID_BRIGHTNESS_STEP_PCT
            )

        return {"extra_fields": vol.Schema(extra_fields)} if extra_fields else {}

    return {}
