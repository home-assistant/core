"""Config validation helper for the script integration."""

from collections.abc import Mapping
from contextlib import suppress
from enum import StrEnum
from typing import Any

import probatio
from probatio.humanize import humanize_error

from homeassistant.components.blueprint import (
    CONF_USE_BLUEPRINT,
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
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import (
    SCRIPT_MODE_SINGLE,
    async_validate_actions_config,
    async_validate_block_collect_errors,
    make_script_schema,
)
from homeassistant.helpers.selector import validate_selector
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.validation_errors import (
    ValidationErrorInfo,
    ValidationErrors,
    iter_validation_errors,
)
from homeassistant.util.yaml.input import UndefinedSubstitution

from .const import (
    CONF_ADVANCED,
    CONF_EXAMPLE,
    CONF_FIELDS,
    CONF_REQUIRED,
    CONF_TRACE,
    DOMAIN,
    LOGGER,
    ScriptService,
)
from .helpers import async_get_blueprints

PACKAGE_MERGE_HINT = "dict"

_MINIMAL_SCRIPT_ENTITY_SCHEMA = probatio.Schema(
    {
        CONF_ALIAS: cv.string,
        probatio.Optional(CONF_DESCRIPTION): cv.string,
    },
    extra=probatio.ALLOW_EXTRA,
)

_INVALID_OBJECT_IDS = {
    ScriptService.RELOAD,
    ScriptService.TURN_OFF,
    ScriptService.TURN_ON,
    ScriptService.TOGGLE,
}

_SCRIPT_OBJECT_ID_SCHEMA = probatio.All(
    cv.slug,
    probatio.NotIn(
        _INVALID_OBJECT_IDS,
        (
            "A script's object_id must not be one of "
            f"{', '.join(sorted(_INVALID_OBJECT_IDS))}"
        ),
    ),
)

SCRIPT_ENTITY_SCHEMA = make_script_schema(
    {
        probatio.Optional(CONF_ALIAS): cv.string,
        probatio.Optional(CONF_TRACE, default={}): TRACE_CONFIG_SCHEMA,
        probatio.Optional(CONF_ICON): cv.icon,
        probatio.Required(CONF_SEQUENCE): cv.SCRIPT_SCHEMA,
        probatio.Optional(CONF_DESCRIPTION, default=""): cv.string,
        probatio.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
        probatio.Optional(CONF_FIELDS, default={}): {
            cv.string: {
                probatio.Optional(CONF_ADVANCED, default=False): cv.boolean,
                probatio.Optional(CONF_DEFAULT): cv.match_all,
                probatio.Optional(CONF_DESCRIPTION): cv.string,
                probatio.Optional(CONF_EXAMPLE): cv.string,
                probatio.Optional(CONF_NAME): cv.string,
                probatio.Optional(CONF_REQUIRED, default=False): cv.boolean,
                probatio.Optional(CONF_SELECTOR): validate_selector,
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
        """Humanize probatio.Invalid, stringify other exceptions."""
        if isinstance(err, probatio.Invalid):
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
        validation_error: str,
    ) -> None:
        """Set validation status."""
        if uses_blueprint:
            validation_status = ValidationStatus.FAILED_BLUEPRINT
        script_config.validation_status = validation_status
        script_config.validation_error = validation_error

    def _minimal_config(
        validation_status: ValidationStatus,
        validation_error: str,
    ) -> ScriptConfig:
        """Try validating id, alias and description."""
        minimal_config = _MINIMAL_SCRIPT_ENTITY_SCHEMA(config)
        script_config = ScriptConfig(minimal_config)
        script_config.raw_blueprint_inputs = raw_blueprint_inputs
        script_config.raw_config = raw_config
        _set_validation_status(script_config, validation_status, validation_error)
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
            return _minimal_config(ValidationStatus.FAILED_BLUEPRINT, str(err))

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
            return _minimal_config(ValidationStatus.FAILED_BLUEPRINT, str(err))

    script_name = f"Script with object id '{object_id}'"
    if isinstance(config, Mapping):
        if CONF_ALIAS in config:
            script_name = f"Script with alias '{config[CONF_ALIAS]}'"

    try:
        _SCRIPT_OBJECT_ID_SCHEMA(object_id)
    except probatio.Invalid as err:
        _log_invalid_script(err, script_name, "has invalid object id", object_id)
        raise
    try:
        validated_config = SCRIPT_ENTITY_SCHEMA(config)
    except probatio.Invalid as err:
        _log_invalid_script(err, script_name, "could not be validated", config)
        if raise_on_errors:
            raise
        return _minimal_config(ValidationStatus.FAILED_SCHEMA, _humanize(err, config))

    script_config = ScriptConfig(validated_config)
    script_config.raw_blueprint_inputs = raw_blueprint_inputs
    script_config.raw_config = raw_config

    try:
        script_config[CONF_SEQUENCE] = await async_validate_actions_config(
            hass, validated_config[CONF_SEQUENCE]
        )
    except (
        probatio.Invalid,
        HomeAssistantError,
    ) as err:
        if isinstance(err, probatio.Invalid):
            err.prepend([CONF_SEQUENCE])
        _log_invalid_script(
            err, script_name, "failed to setup sequence", validated_config
        )
        if raise_on_errors:
            raise
        _set_validation_status(
            script_config,
            ValidationStatus.FAILED_SEQUENCE,
            _humanize(err, validated_config),
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
    except probatio.Invalid, HomeAssistantError:
        return None


async def _async_collect_errors(
    hass: HomeAssistant, config: Any
) -> list[ValidationErrorInfo]:
    """Return all errors of a config item, located in the validated config.

    The errors of the schema come first. They are followed by the errors of
    the sequence which are not among them, also when the schema failed.
    """
    try:
        SCRIPT_ENTITY_SCHEMA(config)
    except probatio.Invalid as err:
        errors = list(iter_validation_errors(err))
    else:
        errors = []

    if not isinstance(config, dict) or CONF_SEQUENCE not in config:
        return errors

    reported = {(info.path, info.message) for info in errors}
    try:
        await async_validate_block_collect_errors(
            hass, "actions", config[CONF_SEQUENCE]
        )
    except ValidationErrors as err:
        errors.extend(
            info
            for info in iter_validation_errors(err, [CONF_SEQUENCE])
            if (info.path, info.message) not in reported
        )
    return errors


async def async_validate_config_item(
    hass: HomeAssistant,
    object_id: str,
    config: dict[str, Any],
) -> ScriptConfig | None:
    """Validate config item, called by EditScriptConfigView.

    Raises ValidationErrors if the config is not valid, with all errors which
    were found. The path of each error is its path in config as it was passed.
    The errors of a blueprint script which are not about a key of config are
    located at use_blueprint.
    """
    try:
        return await _async_validate_config_item(hass, object_id, config, True, False)
    except (probatio.Invalid, HomeAssistantError) as err:
        fail_fast_errors = list(iter_validation_errors(err))

    # Not done in the except block: each error would be chained to the one above
    submitted_keys = set(config) if isinstance(config, dict) else set()
    uses_blueprint = is_blueprint_instance_config(config)
    if uses_blueprint:
        try:
            blueprint_inputs = await async_get_blueprints(
                hass
            ).async_inputs_from_config(config)
            config = blueprint_inputs.async_substitute()
        except BlueprintException, UndefinedSubstitution:
            # No config was generated, the error says why
            raise ValidationErrors(fail_fast_errors) from None

    try:
        _SCRIPT_OBJECT_ID_SCHEMA(object_id)
    except probatio.Invalid as err:
        # Not about the config, so not located at use_blueprint
        raise ValidationErrors(iter_validation_errors(err)) from None

    # Keep the error if validating again does not give any
    errors = await _async_collect_errors(hass, config) or fail_fast_errors
    if not uses_blueprint:
        raise ValidationErrors(errors)
    raise ValidationErrors(
        [
            info
            if info.path and info.path[0] in submitted_keys
            else ValidationErrorInfo(info.exception, (CONF_USE_BLUEPRINT,))
            for info in errors
        ]
    )


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
