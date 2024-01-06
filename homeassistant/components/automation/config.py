"""Config validation helper for the automation integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import blueprint
from homeassistant.components.trace import TRACE_CONFIG_SCHEMA
from homeassistant.config import config_per_platform, config_without_domain
from homeassistant.const import (
    CONF_ALIAS,
    CONF_CONDITION,
    CONF_DESCRIPTION,
    CONF_ID,
    CONF_VARIABLES,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, script
from homeassistant.helpers.condition import async_validate_conditions_config
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.yaml.input import UndefinedSubstitution

from .const import (
    CONF_ACTION,
    CONF_HIDE_ENTITY,
    CONF_INITIAL_STATE,
    CONF_TRACE,
    CONF_TRIGGER,
    CONF_TRIGGER_VARIABLES,
    DOMAIN,
    LOGGER,
)
from .helpers import async_get_blueprints

PACKAGE_MERGE_HINT = "list"

_MINIMAL_PLATFORM_SCHEMA = vol.Schema(
    {
        CONF_ID: str,
        CONF_ALIAS: cv.string,
        vol.Optional(CONF_DESCRIPTION): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HIDE_ENTITY),
    script.make_script_schema(
        {
            # str on purpose
            CONF_ID: str,
            CONF_ALIAS: cv.string,
            vol.Optional(CONF_DESCRIPTION): cv.string,
            vol.Optional(CONF_TRACE, default={}): TRACE_CONFIG_SCHEMA,
            vol.Optional(CONF_INITIAL_STATE): cv.boolean,
            vol.Optional(CONF_HIDE_ENTITY): cv.boolean,
            vol.Required(CONF_TRIGGER): cv.TRIGGER_SCHEMA,
            vol.Optional(CONF_CONDITION): cv.CONDITIONS_SCHEMA,
            vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
            vol.Optional(CONF_TRIGGER_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
            vol.Required(CONF_ACTION): cv.SCRIPT_SCHEMA,
        },
        script.SCRIPT_MODE_SINGLE,
    ),
)


async def _async_validate_config_item(
    hass: HomeAssistant,
    config: ConfigType,
    raise_on_errors: bool,
    warn_on_errors: bool,
) -> AutomationConfig:
    """Validate config item."""
    raw_config = None
    raw_blueprint_inputs = None
    uses_blueprint = False
    with suppress(ValueError):
        raw_config = dict(config)

    def _log_invalid_automation(
        err: Exception,
        automation_name: str,
        problem: str,
        config: ConfigType,
    ) -> None:
        """Log an error about invalid automation."""
        if not warn_on_errors:
            return

        if uses_blueprint:
            LOGGER.error(
                "Blueprint '%s' generated invalid automation with inputs %s: %s",
                blueprint_inputs.blueprint.name,
                blueprint_inputs.inputs,
                humanize_error(config, err) if isinstance(err, vol.Invalid) else err,
            )
            return

        LOGGER.error(
            "%s %s and has been disabled: %s",
            automation_name,
            problem,
            humanize_error(config, err) if isinstance(err, vol.Invalid) else err,
        )
        return

    def _minimal_config() -> AutomationConfig:
        """Try validating id, alias and description."""
        minimal_config = _MINIMAL_PLATFORM_SCHEMA(config)
        automation_config = AutomationConfig(minimal_config)
        automation_config.raw_blueprint_inputs = raw_blueprint_inputs
        automation_config.raw_config = raw_config
        automation_config.validation_failed = True
        return automation_config

    if blueprint.is_blueprint_instance_config(config):
        uses_blueprint = True
        blueprints = async_get_blueprints(hass)
        try:
            blueprint_inputs = await blueprints.async_inputs_from_config(config)
        except blueprint.BlueprintException as err:
            if warn_on_errors:
                LOGGER.error(
                    "Failed to generate automation from blueprint: %s",
                    err,
                )
            if raise_on_errors:
                raise
            return _minimal_config()

        raw_blueprint_inputs = blueprint_inputs.config_with_inputs

        try:
            config = blueprint_inputs.async_substitute()
            raw_config = dict(config)
        except UndefinedSubstitution as err:
            if warn_on_errors:
                LOGGER.error(
                    "Blueprint '%s' failed to generate automation with inputs %s: %s",
                    blueprint_inputs.blueprint.name,
                    blueprint_inputs.inputs,
                    err,
                )
            if raise_on_errors:
                raise HomeAssistantError(err) from err
            return _minimal_config()

    automation_name = "Unnamed automation"
    if isinstance(config, Mapping):
        if CONF_ALIAS in config:
            automation_name = f"Automation with alias '{config[CONF_ALIAS]}'"
        elif CONF_ID in config:
            automation_name = f"Automation with ID '{config[CONF_ID]}'"

    try:
        validated_config = PLATFORM_SCHEMA(config)
    except vol.Invalid as err:
        _log_invalid_automation(err, automation_name, "could not be validated", config)
        if raise_on_errors:
            raise
        return _minimal_config()

    automation_config = AutomationConfig(validated_config)
    automation_config.raw_blueprint_inputs = raw_blueprint_inputs
    automation_config.raw_config = raw_config

    try:
        automation_config[CONF_TRIGGER] = await async_validate_trigger_config(
            hass, validated_config[CONF_TRIGGER]
        )
    except (
        vol.Invalid,
        HomeAssistantError,
    ) as err:
        _log_invalid_automation(
            err, automation_name, "failed to setup triggers", validated_config
        )
        if raise_on_errors:
            raise
        automation_config.validation_failed = True
        return automation_config

    if CONF_CONDITION in validated_config:
        try:
            automation_config[CONF_CONDITION] = await async_validate_conditions_config(
                hass, validated_config[CONF_CONDITION]
            )
        except (
            vol.Invalid,
            HomeAssistantError,
        ) as err:
            _log_invalid_automation(
                err, automation_name, "failed to setup conditions", validated_config
            )
            if raise_on_errors:
                raise
            automation_config.validation_failed = True
            return automation_config

    try:
        automation_config[CONF_ACTION] = await script.async_validate_actions_config(
            hass, validated_config[CONF_ACTION]
        )
    except (
        vol.Invalid,
        HomeAssistantError,
    ) as err:
        _log_invalid_automation(
            err, automation_name, "failed to setup actions", validated_config
        )
        if raise_on_errors:
            raise
        automation_config.validation_failed = True
        return automation_config

    return automation_config


class AutomationConfig(dict):
    """Dummy class to allow adding attributes."""

    raw_config: dict[str, Any] | None = None
    raw_blueprint_inputs: dict[str, Any] | None = None
    validation_failed: bool = False


async def _try_async_validate_config_item(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> AutomationConfig | None:
    """Validate config item."""
    try:
        return await _async_validate_config_item(hass, config, False, True)
    except (vol.Invalid, HomeAssistantError):
        return None


async def async_validate_config_item(
    hass: HomeAssistant,
    config_key: str,
    config: dict[str, Any],
) -> AutomationConfig | None:
    """Validate config item, called by EditAutomationConfigView."""
    return await _async_validate_config_item(hass, config, True, False)


async def async_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    automations = list(
        filter(
            lambda x: x is not None,
            await asyncio.gather(
                *(
                    _try_async_validate_config_item(hass, p_config)
                    for _, p_config in config_per_platform(config, DOMAIN)
                )
            ),
        )
    )

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = automations

    return config
