"""Config validation helper for the script integration."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from enum import StrEnum
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components.blueprint import (
    BlueprintException,
    is_blueprint_instance_config,
)
from homeassistant.components.trace import TRACE_CONFIG_SCHEMA
from homeassistant.config import config_per_platform, config_without_domain
from homeassistant.const import (
    CONF_ALIAS,
    CONF_DEFAULT,
    CONF_DESCRIPTION,
    CONF_ICON,
    CONF_NAME,
    CONF_SELECTOR,
    CONF_SEQUENCE,
    CONF_VARIABLES,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import (
    SCRIPT_MODE_SINGLE,
    async_validate_actions_config,
    make_script_schema,
)
from homeassistant.helpers.selector import validate_selector
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.yaml.input import UndefinedSubstitution

from .const import (
    CONF_ADVANCED,
    CONF_EXAMPLE,
    CONF_FIELDS,
    CONF_REQUIRED,
    CONF_TRACE,
    DOMAIN,
    LOGGER,
)
from .helpers import async_get_blueprints

PACKAGE_MERGE_HINT = "dict"

_MINIMAL_SCRIPT_ENTITY_SCHEMA = vol.Schema(
    {
        CONF_ALIAS: cv.string,
        vol.Optional(CONF_DESCRIPTION): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

_INVALID_OBJECT_IDS = {
    SERVICE_RELOAD,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_TOGGLE,
}

_SCRIPT_OBJECT_ID_SCHEMA = vol.All(
    cv.slug,
    vol.NotIn(
        _INVALID_OBJECT_IDS,
        (
            "A script's object_id must not be one of "
            f"{', '.join(sorted(_INVALID_OBJECT_IDS))}"
        ),
    ),
)

SCRIPT_ENTITY_SCHEMA = make_script_schema(
    {
        vol.Optional(CONF_ALIAS): cv.string,
        vol.Optional(CONF_TRACE, default={}): TRACE_CONFIG_SCHEMA,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Required(CONF_SEQUENCE): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DESCRIPTION, default=""): cv.string,
        vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
        vol.Optional(CONF_FIELDS, default={}): {
            cv.string: {
                vol.Optional(CONF_ADVANCED, default=False): cv.boolean,
                vol.Optional(CONF_DEFAULT): cv.match_all,
                vol.Optional(CONF_DESCRIPTION): cv.string,
                vol.Optional(CONF_EXAMPLE): cv.string,
                vol.Optional(CONF_NAME): cv.string,
                vol.Optional(CONF_REQUIRED, default=False): cv.boolean,
                vol.Optional(CONF_SELECTOR): validate_selector,
            }
        },
    },
    SCRIPT_MODE_SINGLE,
)


async def _async_validate_config_item(
    hass: HomeAssistant,
    object_id: str,
    config: ConfigType,
    raise_on_errors: bool,
    warn_on_errors: bool,
) -> ScriptConfig:
    """Validate config item."""
    raw_config = None
    raw_blueprint_inputs = None
    uses_blueprint = False
    with suppress(ValueError):  # Invalid config
        raw_config = dict(config)

    def _humanize(err: Exception, data: Any) -> str:
        """Humanize vol.Invalid, stringify other exceptions."""
        if isinstance(err, vol.Invalid):
            return humanize_error(data, err)
        return str(err)

    def _log_invalid_script(
        err: Exception,
        script_name: str,
        problem: str,
        data: Any,
    ) -> None:
        """Log an error about invalid script."""
        if not warn_on_errors:
            return

        if uses_blueprint:
            LOGGER.error(
                "Blueprint '%s' generated invalid script with inputs %s: %s",
                blueprint_inputs.blueprint.name,
                blueprint_inputs.inputs,
                _humanize(err, data),
            )
            return

        LOGGER.error(
            "%s %s and has been disabled: %s",
            script_name,
            problem,
            _humanize(err, data),
        )
        return

    def _set_validation_status(
        script_config: ScriptConfig,
        validation_status: ValidationStatus,
        validation_error: Exception,
        config: ConfigType,
    ) -> None:
        """Set validation status."""
        if uses_blueprint:
            validation_status = ValidationStatus.FAILED_BLUEPRINT
        script_config.validation_status = validation_status
        script_config.validation_error = _humanize(validation_error, config)

    def _minimal_config(
        validation_status: ValidationStatus,
        validation_error: Exception,
        config: ConfigType,
    ) -> ScriptConfig:
        """Try validating id, alias and description."""
        minimal_config = _MINIMAL_SCRIPT_ENTITY_SCHEMA(config)
        script_config = ScriptConfig(minimal_config)
        script_config.raw_blueprint_inputs = raw_blueprint_inputs
        script_config.raw_config = raw_config
        _set_validation_status(
            script_config, validation_status, validation_error, config
        )
        return script_config

    if is_blueprint_instance_config(config):
        uses_blueprint = True
        blueprints = async_get_blueprints(hass)
        try:
            blueprint_inputs = await blueprints.async_inputs_from_config(config)
        except BlueprintException as err:
            if warn_on_errors:
                LOGGER.error(
                    "Failed to generate script from blueprint: %s",
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
                    "Blueprint '%s' failed to generate script with inputs %s: %s",
                    blueprint_inputs.blueprint.name,
                    blueprint_inputs.inputs,
                    err,
                )
            if raise_on_errors:
                raise HomeAssistantError(err) from err
            return _minimal_config(ValidationStatus.FAILED_BLUEPRINT, err, config)

    script_name = f"Script with object id '{object_id}'"
    if isinstance(config, Mapping):
        if CONF_ALIAS in config:
            script_name = f"Script with alias '{config[CONF_ALIAS]}'"

    try:
        _SCRIPT_OBJECT_ID_SCHEMA(object_id)
    except vol.Invalid as err:
        _log_invalid_script(err, script_name, "has invalid object id", object_id)
        raise
    try:
        validated_config = SCRIPT_ENTITY_SCHEMA(config)
    except vol.Invalid as err:
        _log_invalid_script(err, script_name, "could not be validated", config)
        if raise_on_errors:
            raise
        return _minimal_config(ValidationStatus.FAILED_SCHEMA, err, config)

    script_config = ScriptConfig(validated_config)
    script_config.raw_blueprint_inputs = raw_blueprint_inputs
    script_config.raw_config = raw_config

    try:
        script_config[CONF_SEQUENCE] = await async_validate_actions_config(
            hass, validated_config[CONF_SEQUENCE]
        )
    except (
        vol.Invalid,
        HomeAssistantError,
    ) as err:
        _log_invalid_script(
            err, script_name, "failed to setup sequence", validated_config
        )
        if raise_on_errors:
            raise
        _set_validation_status(
            script_config, ValidationStatus.FAILED_SEQUENCE, err, validated_config
        )
        return script_config

    return script_config


class ValidationStatus(StrEnum):
    """What was changed in a config entry."""

    FAILED_BLUEPRINT = "failed_blueprint"
    FAILED_SCHEMA = "failed_schema"
    FAILED_SEQUENCE = "failed_sequence"
    OK = "ok"


class ScriptConfig(dict):
    """Dummy class to allow adding attributes."""

    raw_config: ConfigType | None = None
    raw_blueprint_inputs: ConfigType | None = None
    validation_status: ValidationStatus = ValidationStatus.OK
    validation_error: str | None = None


async def _try_async_validate_config_item(
    hass: HomeAssistant,
    object_id: str,
    config: ConfigType,
) -> ScriptConfig | None:
    """Validate config item."""
    try:
        return await _async_validate_config_item(hass, object_id, config, False, True)
    except (vol.Invalid, HomeAssistantError):
        return None


async def async_validate_config_item(
    hass: HomeAssistant,
    object_id: str,
    config: dict[str, Any],
) -> ScriptConfig | None:
    """Validate config item, called by EditScriptConfigView."""
    return await _async_validate_config_item(hass, object_id, config, True, False)


async def async_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    scripts = {}
    for _, p_config in config_per_platform(config, DOMAIN):
        for object_id, cfg in p_config.items():
            if object_id in scripts:
                LOGGER.warning("Duplicate script detected with name: '%s'", object_id)
                continue
            cfg = await _try_async_validate_config_item(hass, object_id, cfg)
            if cfg is not None:
                scripts[object_id] = cfg

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = scripts

    return config
