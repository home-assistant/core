"""Config validation helper for the automation integration."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from enum import StrEnum
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import blueprint
from homeassistant.components.trace import TRACE_CONFIG_SCHEMA
from homeassistant.config import config_per_platform, config_without_domain
from homeassistant.const import (
    CONF_ALIAS,
    CONF_CONDITION,
    CONF_CONDITIONS,
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
    CONF_ACTIONS,
    CONF_HIDE_ENTITY,
    CONF_INITIAL_STATE,
    CONF_TRACE,
    CONF_TRIGGER,
    CONF_TRIGGER_VARIABLES,
    CONF_TRIGGERS,
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


def _backward_compat_schema(value: Any | None) -> Any:
    """Backward compatibility for automations."""

    value = cv.renamed(CONF_TRIGGER, CONF_TRIGGERS)(value)
    value = cv.renamed(CONF_ACTION, CONF_ACTIONS)(value)
    return cv.renamed(CONF_CONDITION, CONF_CONDITIONS)(value)


PLATFORM_SCHEMA = vol.All(
    _backward_compat_schema,
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
            vol.Required(CONF_TRIGGERS): cv.TRIGGER_SCHEMA,
            vol.Optional(CONF_CONDITIONS): cv.CONDITIONS_SCHEMA,
            vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
            vol.Optional(CONF_TRIGGER_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
            vol.Required(CONF_ACTIONS): cv.SCRIPT_SCHEMA,
        },
        script.SCRIPT_MODE_SINGLE,
    ),
)

AUTOMATION_BLUEPRINT_SCHEMA = vol.All(
    _backward_compat_schema, blueprint.schemas.BLUEPRINT_SCHEMA
)


async def _async_validate_config_item(  # noqa: C901
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

    def _humanize(err: Exception, config: ConfigType) -> str:
        """Humanize vol.Invalid, stringify other exceptions."""
        if isinstance(err, vol.Invalid):
            return humanize_error(config, err)
        return str(err)

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
                _humanize(err, config),
            )
            return

        LOGGER.error(
            "%s %s and has been disabled: %s",
            automation_name,
            problem,
            _humanize(err, config),
        )
        return

    def _set_validation_status(
        automation_config: AutomationConfig,
        validation_status: ValidationStatus,
        validation_error: Exception,
        config: ConfigType,
    ) -> None:
        """Set validation status."""
        if uses_blueprint:
            validation_status = ValidationStatus.FAILED_BLUEPRINT
        automation_config.validation_status = validation_status
        automation_config.validation_error = _humanize(validation_error, config)

    def _minimal_config(
        validation_status: ValidationStatus,
        validation_error: Exception,
        config: ConfigType,
    ) -> AutomationConfig:
        """Try validating id, alias and description."""
        minimal_config = _MINIMAL_PLATFORM_SCHEMA(config)
        automation_config = AutomationConfig(minimal_config)
        automation_config.raw_blueprint_inputs = raw_blueprint_inputs
        automation_config.raw_config = raw_config
        _set_validation_status(
            automation_config, validation_status, validation_error, config
        )
        return automation_config

    if blueprint.is_blueprint_instance_config(config):
        uses_blueprint = True
        blueprints = async_get_blueprints(hass)
        try:
            blueprint_inputs = await blueprints.async_inputs_from_config(
                _backward_compat_schema(config)
            )
        except blueprint.BlueprintException as err:
            if warn_on_errors:
                LOGGER.error(
                    "Failed to generate automation from blueprint: %s",
                    err,
                )
            if raise_on_errors:
                raise
            return _minimal_config(ValidationStatus.FAILED_BLUEPRINT, err, config)

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
            return _minimal_config(ValidationStatus.FAILED_BLUEPRINT, err, config)

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
        return _minimal_config(ValidationStatus.FAILED_SCHEMA, err, config)

    automation_config = AutomationConfig(validated_config)
    automation_config.raw_blueprint_inputs = raw_blueprint_inputs
    automation_config.raw_config = raw_config

    try:
        automation_config[CONF_TRIGGERS] = await async_validate_trigger_config(
            hass, validated_config[CONF_TRIGGERS]
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
        _set_validation_status(
            automation_config, ValidationStatus.FAILED_TRIGGERS, err, validated_config
        )
        return automation_config

    if CONF_CONDITIONS in validated_config:
        try:
            automation_config[CONF_CONDITIONS] = await async_validate_conditions_config(
                hass, validated_config[CONF_CONDITIONS]
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
            _set_validation_status(
                automation_config,
                ValidationStatus.FAILED_CONDITIONS,
                err,
                validated_config,
            )
            return automation_config

    try:
        automation_config[CONF_ACTIONS] = await script.async_validate_actions_config(
            hass, validated_config[CONF_ACTIONS]
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
        _set_validation_status(
            automation_config, ValidationStatus.FAILED_ACTIONS, err, validated_config
        )
        return automation_config

    return automation_config


class ValidationStatus(StrEnum):
    """What was changed in a config entry."""

    FAILED_ACTIONS = "failed_actions"
    FAILED_BLUEPRINT = "failed_blueprint"
    FAILED_CONDITIONS = "failed_conditions"
    FAILED_SCHEMA = "failed_schema"
    FAILED_TRIGGERS = "failed_triggers"
    OK = "ok"


class AutomationConfig(dict):
    """Dummy class to allow adding attributes."""

    raw_config: dict[str, Any] | None = None
    raw_blueprint_inputs: dict[str, Any] | None = None
    validation_status: ValidationStatus = ValidationStatus.OK
    validation_error: str | None = None


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
    # No gather here since _try_async_validate_config_item is unlikely to suspend
    # and the cost of creating many tasks is not worth the benefit.
    automations = list(
        filter(
            lambda x: x is not None,
            [
                await _try_async_validate_config_item(hass, p_config)
                for _, p_config in config_per_platform(config, DOMAIN)
            ],
        )
    )

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = automations

    return config
