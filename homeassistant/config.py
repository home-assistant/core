"""Module to help with parsing and generating configuration files."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from functools import partial, reduce
import logging
import operator
import os
from pathlib import Path
import re
import shutil
from types import ModuleType
from typing import TYPE_CHECKING, Any

from awesomeversion import AwesomeVersion
import voluptuous as vol
from voluptuous.humanize import MAX_VALIDATION_ERROR_ITEM_LENGTH
from yaml.error import MarkedYAMLError

from .const import CONF_PACKAGES, CONF_PLATFORM, __version__
from .core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from .core_config import _PACKAGE_DEFINITION_SCHEMA, _PACKAGES_CONFIG_SCHEMA
from .exceptions import ConfigValidationError, HomeAssistantError
from .helpers import config_validation as cv
from .helpers.translation import async_get_exception_message
from .helpers.typing import ConfigType
from .loader import ComponentProtocol, Integration, IntegrationNotFound
from .requirements import RequirementsNotFound, async_get_integration_with_requirements
from .util.async_ import create_eager_task
from .util.package import is_docker_env
from .util.yaml import SECRET_YAML, Secrets, YamlTypeError, load_yaml_dict
from .util.yaml.objects import NodeStrClass

_LOGGER = logging.getLogger(__name__)

RE_YAML_ERROR = re.compile(r"homeassistant\.util\.yaml")
RE_ASCII = re.compile(r"\033\[[^m]*m")
YAML_CONFIG_FILE = "configuration.yaml"
VERSION_FILE = ".HA_VERSION"
CONFIG_DIR_NAME = ".homeassistant"

AUTOMATION_CONFIG_PATH = "automations.yaml"
SCRIPT_CONFIG_PATH = "scripts.yaml"
SCENE_CONFIG_PATH = "scenes.yaml"

LOAD_EXCEPTIONS = (ImportError, FileNotFoundError)
INTEGRATION_LOAD_EXCEPTIONS = (IntegrationNotFound, RequirementsNotFound)

SAFE_MODE_FILENAME = "safe-mode"

DEFAULT_CONFIG = f"""
# Loads default set of integrations. Do not remove.
default_config:

# Load frontend themes from the themes folder
frontend:
  themes: !include_dir_merge_named themes

automation: !include {AUTOMATION_CONFIG_PATH}
script: !include {SCRIPT_CONFIG_PATH}
scene: !include {SCENE_CONFIG_PATH}
"""
DEFAULT_SECRETS = """
# Use this file to store secrets like usernames and passwords.
# Learn more at https://www.home-assistant.io/docs/configuration/secrets/
some_password: welcome
"""
TTS_PRE_92 = """
tts:
  - platform: google
"""
TTS_92 = """
tts:
  - platform: google_translate
    service_name: google_say
"""


class ConfigErrorTranslationKey(StrEnum):
    """Config error translation keys for config errors."""

    # translation keys with a generated config related message text
    CONFIG_VALIDATION_ERR = "config_validation_err"
    PLATFORM_CONFIG_VALIDATION_ERR = "platform_config_validation_err"

    # translation keys with a general static message text
    COMPONENT_IMPORT_ERR = "component_import_err"
    CONFIG_PLATFORM_IMPORT_ERR = "config_platform_import_err"
    CONFIG_VALIDATOR_UNKNOWN_ERR = "config_validator_unknown_err"
    CONFIG_SCHEMA_UNKNOWN_ERR = "config_schema_unknown_err"
    PLATFORM_COMPONENT_LOAD_ERR = "platform_component_load_err"
    PLATFORM_COMPONENT_LOAD_EXC = "platform_component_load_exc"
    PLATFORM_SCHEMA_VALIDATOR_ERR = "platform_schema_validator_err"

    # translation key in case multiple errors occurred
    MULTIPLE_INTEGRATION_CONFIG_ERRORS = "multiple_integration_config_errors"


_CONFIG_LOG_SHOW_STACK_TRACE: dict[ConfigErrorTranslationKey, bool] = {
    ConfigErrorTranslationKey.COMPONENT_IMPORT_ERR: False,
    ConfigErrorTranslationKey.CONFIG_PLATFORM_IMPORT_ERR: False,
    ConfigErrorTranslationKey.CONFIG_VALIDATOR_UNKNOWN_ERR: True,
    ConfigErrorTranslationKey.CONFIG_SCHEMA_UNKNOWN_ERR: True,
    ConfigErrorTranslationKey.PLATFORM_COMPONENT_LOAD_ERR: False,
    ConfigErrorTranslationKey.PLATFORM_COMPONENT_LOAD_EXC: True,
    ConfigErrorTranslationKey.PLATFORM_SCHEMA_VALIDATOR_ERR: True,
}


@dataclass
class ConfigExceptionInfo:
    """Configuration exception info class."""

    exception: Exception
    translation_key: ConfigErrorTranslationKey
    platform_path: str
    config: ConfigType
    integration_link: str | None


@dataclass
class IntegrationConfigInfo:
    """Configuration for an integration and exception information."""

    config: ConfigType | None
    exception_info_list: list[ConfigExceptionInfo]


def get_default_config_dir() -> str:
    """Put together the default configuration directory based on the OS."""
    data_dir = os.path.expanduser("~")
    return os.path.join(data_dir, CONFIG_DIR_NAME)


async def async_ensure_config_exists(hass: HomeAssistant) -> bool:
    """Ensure a configuration file exists in given configuration directory.

    Creating a default one if needed.
    Return boolean if configuration dir is ready to go.
    """
    config_path = hass.config.path(YAML_CONFIG_FILE)

    if os.path.isfile(config_path):
        return True

    print(  # noqa: T201
        "Unable to find configuration. Creating default one in", hass.config.config_dir
    )
    return await async_create_default_config(hass)


async def async_create_default_config(hass: HomeAssistant) -> bool:
    """Create a default configuration file in given configuration directory.

    Return if creation was successful.
    """
    return await hass.async_add_executor_job(
        _write_default_config, hass.config.config_dir
    )


def _write_default_config(config_dir: str) -> bool:
    """Write the default config."""
    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)
    secret_path = os.path.join(config_dir, SECRET_YAML)
    version_path = os.path.join(config_dir, VERSION_FILE)
    automation_yaml_path = os.path.join(config_dir, AUTOMATION_CONFIG_PATH)
    script_yaml_path = os.path.join(config_dir, SCRIPT_CONFIG_PATH)
    scene_yaml_path = os.path.join(config_dir, SCENE_CONFIG_PATH)

    # Writing files with YAML does not create the most human readable results
    # So we're hard coding a YAML template.
    try:
        with open(config_path, "w", encoding="utf8") as config_file:
            config_file.write(DEFAULT_CONFIG)

        if not os.path.isfile(secret_path):
            with open(secret_path, "w", encoding="utf8") as secret_file:
                secret_file.write(DEFAULT_SECRETS)

        with open(version_path, "w", encoding="utf8") as version_file:
            version_file.write(__version__)

        if not os.path.isfile(automation_yaml_path):
            with open(automation_yaml_path, "w", encoding="utf8") as automation_file:
                automation_file.write("[]")

        if not os.path.isfile(script_yaml_path):
            with open(script_yaml_path, "w", encoding="utf8"):
                pass

        if not os.path.isfile(scene_yaml_path):
            with open(scene_yaml_path, "w", encoding="utf8"):
                pass
    except OSError:
        print(  # noqa: T201
            f"Unable to create default configuration file {config_path}"
        )
        return False
    return True


async def async_hass_config_yaml(hass: HomeAssistant) -> dict:
    """Load YAML from a Home Assistant configuration file.

    This function allows a component inside the asyncio loop to reload its
    configuration by itself. Include package merge.
    """
    secrets = Secrets(Path(hass.config.config_dir))

    # Not using async_add_executor_job because this is an internal method.
    try:
        config = await hass.loop.run_in_executor(
            None,
            load_yaml_config_file,
            hass.config.path(YAML_CONFIG_FILE),
            secrets,
        )
    except HomeAssistantError as exc:
        if not (base_exc := exc.__cause__) or not isinstance(base_exc, MarkedYAMLError):
            raise

        # Rewrite path to offending YAML file to be relative the hass config dir
        if base_exc.context_mark and base_exc.context_mark.name:
            base_exc.context_mark.name = _relpath(hass, base_exc.context_mark.name)
        if base_exc.problem_mark and base_exc.problem_mark.name:
            base_exc.problem_mark.name = _relpath(hass, base_exc.problem_mark.name)
        raise

    invalid_domains = []
    for key in config:
        try:
            cv.domain_key(key)
        except vol.Invalid as exc:
            suffix = ""
            if annotation := find_annotation(config, exc.path):
                suffix = f" at {_relpath(hass, annotation[0])}, line {annotation[1]}"
            _LOGGER.error("Invalid domain '%s'%s", key, suffix)
            invalid_domains.append(key)
    for invalid_domain in invalid_domains:
        config.pop(invalid_domain)

    core_config = config.get(HOMEASSISTANT_DOMAIN, {})
    try:
        await merge_packages_config(hass, config, core_config.get(CONF_PACKAGES, {}))
    except vol.Invalid as exc:
        suffix = ""
        if annotation := find_annotation(
            config, [HOMEASSISTANT_DOMAIN, CONF_PACKAGES, *exc.path]
        ):
            suffix = f" at {_relpath(hass, annotation[0])}, line {annotation[1]}"
        _LOGGER.error(
            "Invalid package configuration '%s'%s: %s", CONF_PACKAGES, suffix, exc
        )
        core_config[CONF_PACKAGES] = {}

    return config


def load_yaml_config_file(
    config_path: str, secrets: Secrets | None = None
) -> dict[Any, Any]:
    """Parse a YAML configuration file.

    Raises FileNotFoundError or HomeAssistantError.

    This method needs to run in an executor.
    """
    try:
        conf_dict = load_yaml_dict(config_path, secrets)
    except YamlTypeError as exc:
        msg = (
            f"The configuration file {os.path.basename(config_path)} "
            "does not contain a dictionary"
        )
        _LOGGER.error(msg)
        raise HomeAssistantError(msg) from exc

    # Convert values to dictionaries if they are None
    for key, value in conf_dict.items():
        conf_dict[key] = value or {}
    return conf_dict


def process_ha_config_upgrade(hass: HomeAssistant) -> None:
    """Upgrade configuration if necessary.

    This method needs to run in an executor.
    """
    version_path = hass.config.path(VERSION_FILE)

    try:
        with open(version_path, encoding="utf8") as inp:
            conf_version = inp.readline().strip()
    except FileNotFoundError:
        # Last version to not have this file
        conf_version = "0.7.7"

    if conf_version == __version__:
        return

    _LOGGER.info(
        "Upgrading configuration directory from %s to %s", conf_version, __version__
    )

    version_obj = AwesomeVersion(conf_version)

    if version_obj < AwesomeVersion("0.50"):
        # 0.50 introduced persistent deps dir.
        lib_path = hass.config.path("deps")
        if os.path.isdir(lib_path):
            shutil.rmtree(lib_path)

    if version_obj < AwesomeVersion("0.92"):
        # 0.92 moved google/tts.py to google_translate/tts.py
        config_path = hass.config.path(YAML_CONFIG_FILE)

        with open(config_path, encoding="utf-8") as config_file:
            config_raw = config_file.read()

        if TTS_PRE_92 in config_raw:
            _LOGGER.info("Migrating google tts to google_translate tts")
            config_raw = config_raw.replace(TTS_PRE_92, TTS_92)
            try:
                with open(config_path, "w", encoding="utf-8") as config_file:
                    config_file.write(config_raw)
            except OSError:
                _LOGGER.exception("Migrating to google_translate tts failed")

    if version_obj < AwesomeVersion("0.94") and is_docker_env():
        # In 0.94 we no longer install packages inside the deps folder when
        # running inside a Docker container.
        lib_path = hass.config.path("deps")
        if os.path.isdir(lib_path):
            shutil.rmtree(lib_path)

    with open(version_path, "w", encoding="utf8") as outp:
        outp.write(__version__)


@callback
def async_log_schema_error(
    exc: vol.Invalid,
    domain: str,
    config: dict,
    hass: HomeAssistant,
    link: str | None = None,
) -> None:
    """Log a schema validation error."""
    message = format_schema_error(hass, exc, domain, config, link)
    _LOGGER.error(message)


@callback
def async_log_config_validator_error(
    exc: vol.Invalid | HomeAssistantError,
    domain: str,
    config: dict,
    hass: HomeAssistant,
    link: str | None = None,
) -> None:
    """Log an error from a custom config validator."""
    if isinstance(exc, vol.Invalid):
        async_log_schema_error(exc, domain, config, hass, link)
        return

    message = format_homeassistant_error(hass, exc, domain, config, link)
    _LOGGER.error(message, exc_info=exc)


def _get_annotation(item: Any) -> tuple[str, int | str] | None:
    if not hasattr(item, "__config_file__"):
        return None

    return (getattr(item, "__config_file__"), getattr(item, "__line__", "?"))


def _get_by_path(data: dict | list, items: list[Hashable]) -> Any:
    """Access a nested object in root by item sequence.

    Returns None in case of error.
    """
    try:
        return reduce(operator.getitem, items, data)  # type: ignore[arg-type]
    except (KeyError, IndexError, TypeError):
        return None


def find_annotation(
    config: dict | list, path: list[Hashable]
) -> tuple[str, int | str] | None:
    """Find file/line annotation for a node in config pointed to by path.

    If the node pointed to is a dict or list, prefer the annotation for the key in
    the key/value pair defining the dict or list.
    If the node is not annotated, try the parent node.
    """

    def find_annotation_for_key(
        item: dict, path: list[Hashable], tail: Hashable
    ) -> tuple[str, int | str] | None:
        for key in item:
            if key == tail:
                if annotation := _get_annotation(key):
                    return annotation
                break
        return None

    def find_annotation_rec(
        config: dict | list, path: list[Hashable], tail: Hashable | None
    ) -> tuple[str, int | str] | None:
        item = _get_by_path(config, path)
        if isinstance(item, dict) and tail is not None:
            if tail_annotation := find_annotation_for_key(item, path, tail):
                return tail_annotation

        if (
            isinstance(item, (dict, list))
            and path
            and (
                key_annotation := find_annotation_for_key(
                    _get_by_path(config, path[:-1]), path[:-1], path[-1]
                )
            )
        ):
            return key_annotation

        if annotation := _get_annotation(item):
            return annotation

        if not path:
            return None

        tail = path.pop()
        if annotation := find_annotation_rec(config, path, tail):
            return annotation
        return _get_annotation(item)

    return find_annotation_rec(config, list(path), None)


def _relpath(hass: HomeAssistant, path: str) -> str:
    """Return path relative to the Home Assistant config dir."""
    return os.path.relpath(path, hass.config.config_dir)


def stringify_invalid(
    hass: HomeAssistant,
    exc: vol.Invalid,
    domain: str,
    config: dict,
    link: str | None,
    max_sub_error_length: int,
) -> str:
    """Stringify voluptuous.Invalid.

    This is an alternative to the custom __str__ implemented in
    voluptuous.error.Invalid. The modifications are:
    - Format the path delimited by -> instead of @data[]
    - Prefix with domain, file and line of the error
    - Suffix with a link to the documentation
    - Give a more user friendly output for unknown options
    - Give a more user friendly output for missing options
    """
    if "." in domain:
        integration_domain, _, platform_domain = domain.partition(".")
        message_prefix = (
            f"Invalid config for '{platform_domain}' from integration "
            f"'{integration_domain}'"
        )
    else:
        message_prefix = f"Invalid config for '{domain}'"
    if domain != HOMEASSISTANT_DOMAIN and link:
        message_suffix = f", please check the docs at {link}"
    else:
        message_suffix = ""
    if annotation := find_annotation(config, exc.path):
        message_prefix += f" at {_relpath(hass, annotation[0])}, line {annotation[1]}"
    path = "->".join(str(m) for m in exc.path)
    if exc.error_message == "extra keys not allowed":
        return (
            f"{message_prefix}: '{exc.path[-1]}' is an invalid option for '{domain}', "
            f"check: {path}{message_suffix}"
        )
    if exc.error_message == "required key not provided":
        return (
            f"{message_prefix}: required key '{exc.path[-1]}' not provided"
            f"{message_suffix}"
        )
    # This function is an alternative to the stringification done by
    # vol.Invalid.__str__, so we need to call Exception.__str__ here
    # instead of str(exc)
    output = Exception.__str__(exc)
    if error_type := exc.error_type:
        output += " for " + error_type
    offending_item_summary = repr(_get_by_path(config, exc.path))
    if len(offending_item_summary) > max_sub_error_length:
        offending_item_summary = (
            f"{offending_item_summary[: max_sub_error_length - 3]}..."
        )
    return (
        f"{message_prefix}: {output} '{path}', got {offending_item_summary}"
        f"{message_suffix}"
    )


def humanize_error(
    hass: HomeAssistant,
    validation_error: vol.Invalid,
    domain: str,
    config: dict,
    link: str | None,
    max_sub_error_length: int = MAX_VALIDATION_ERROR_ITEM_LENGTH,
) -> str:
    """Provide a more helpful + complete validation error message.

    This is a modified version of voluptuous.error.Invalid.__str__,
    the modifications make some minor changes to the formatting.
    """
    if isinstance(validation_error, vol.MultipleInvalid):
        return "\n".join(
            sorted(
                humanize_error(
                    hass, sub_error, domain, config, link, max_sub_error_length
                )
                for sub_error in validation_error.errors
            )
        )
    return stringify_invalid(
        hass, validation_error, domain, config, link, max_sub_error_length
    )


@callback
def format_homeassistant_error(
    hass: HomeAssistant,
    exc: HomeAssistantError,
    domain: str,
    config: dict,
    link: str | None = None,
) -> str:
    """Format HomeAssistantError thrown by a custom config validator."""
    if "." in domain:
        integration_domain, _, platform_domain = domain.partition(".")
        message_prefix = (
            f"Invalid config for '{platform_domain}' from integration "
            f"'{integration_domain}'"
        )
    else:
        message_prefix = f"Invalid config for '{domain}'"
    # HomeAssistantError raised by custom config validator has no path to the
    # offending configuration key, use the domain key as path instead.
    if annotation := find_annotation(config, [domain]):
        message_prefix += f" at {_relpath(hass, annotation[0])}, line {annotation[1]}"
    message = f"{message_prefix}: {str(exc) or repr(exc)}"
    if domain != HOMEASSISTANT_DOMAIN and link:
        message += f", please check the docs at {link}"

    return message


@callback
def format_schema_error(
    hass: HomeAssistant,
    exc: vol.Invalid,
    domain: str,
    config: dict,
    link: str | None = None,
) -> str:
    """Format configuration validation error."""
    return humanize_error(hass, exc, domain, config, link)


def _log_pkg_error(
    hass: HomeAssistant, package: str, component: str | None, config: dict, message: str
) -> None:
    """Log an error while merging packages."""
    message_prefix = f"Setup of package '{package}'"
    if annotation := find_annotation(
        config, [HOMEASSISTANT_DOMAIN, CONF_PACKAGES, package]
    ):
        message_prefix += f" at {_relpath(hass, annotation[0])}, line {annotation[1]}"

    _LOGGER.error("%s failed: %s", message_prefix, message)


def _identify_config_schema(module: ComponentProtocol) -> str | None:
    """Extract the schema and identify list or dict based."""
    if not isinstance(module.CONFIG_SCHEMA, vol.Schema):
        return None  # type: ignore[unreachable]

    schema = module.CONFIG_SCHEMA.schema

    if isinstance(schema, vol.All):
        for subschema in schema.validators:
            if isinstance(subschema, dict):
                schema = subschema
                break
        else:
            return None

    try:
        key = next(k for k in schema if k == module.DOMAIN)
    except (TypeError, AttributeError, StopIteration):
        return None
    except Exception:
        _LOGGER.exception("Unexpected error identifying config schema")
        return None

    if hasattr(key, "default") and not isinstance(
        key.default, vol.schema_builder.Undefined
    ):
        default_value = module.CONFIG_SCHEMA({module.DOMAIN: key.default()})[
            module.DOMAIN
        ]

        if isinstance(default_value, dict):
            return "dict"

        if isinstance(default_value, list):
            return "list"

        return None

    domain_schema = schema[key]

    t_schema = str(domain_schema)
    if t_schema.startswith("{") or "schema_with_slug_keys" in t_schema:
        return "dict"
    if t_schema.startswith(("[", "All(<function ensure_list")):
        return "list"
    return None


def _validate_package_definition(name: str, conf: Any) -> None:
    """Validate basic package definition properties."""
    cv.slug(name)
    _PACKAGE_DEFINITION_SCHEMA(conf)


def _recursive_merge(conf: dict[str, Any], package: dict[str, Any]) -> str | None:
    """Merge package into conf, recursively."""
    duplicate_key: str | None = None
    for key, pack_conf in package.items():
        if isinstance(pack_conf, dict):
            if not pack_conf:
                continue
            conf[key] = conf.get(key, OrderedDict())
            duplicate_key = _recursive_merge(conf=conf[key], package=pack_conf)

        elif isinstance(pack_conf, list):
            conf[key] = cv.remove_falsy(
                cv.ensure_list(conf.get(key)) + cv.ensure_list(pack_conf)
            )

        else:
            if conf.get(key) is not None:
                return key
            conf[key] = pack_conf
    return duplicate_key


async def merge_packages_config(
    hass: HomeAssistant,
    config: dict,
    packages: dict[str, Any],
    _log_pkg_error: Callable[
        [HomeAssistant, str, str | None, dict, str], None
    ] = _log_pkg_error,
) -> dict:
    """Merge packages into the top-level configuration.

    Ignores packages that cannot be setup. Mutates config. Raises
    vol.Invalid if whole package config is invalid.
    """

    _PACKAGES_CONFIG_SCHEMA(packages)

    invalid_packages = []
    for pack_name, pack_conf in packages.items():
        try:
            _validate_package_definition(pack_name, pack_conf)
        except vol.Invalid as exc:
            _log_pkg_error(
                hass,
                pack_name,
                None,
                config,
                f"Invalid package definition '{pack_name}': {exc!s}. Package "
                f"will not be initialized",
            )
            invalid_packages.append(pack_name)
            continue

        for comp_name, comp_conf in pack_conf.items():
            if comp_name == HOMEASSISTANT_DOMAIN:
                continue
            try:
                domain = cv.domain_key(comp_name)
            except vol.Invalid:
                _log_pkg_error(
                    hass, pack_name, comp_name, config, f"Invalid domain '{comp_name}'"
                )
                continue

            try:
                integration = await async_get_integration_with_requirements(
                    hass, domain
                )
                component = await integration.async_get_component()
            except LOAD_EXCEPTIONS as exc:
                _log_pkg_error(
                    hass,
                    pack_name,
                    comp_name,
                    config,
                    f"Integration {comp_name} caused error: {exc!s}",
                )
                continue
            except INTEGRATION_LOAD_EXCEPTIONS as exc:
                _log_pkg_error(hass, pack_name, comp_name, config, str(exc))
                continue

            try:
                config_platform: (
                    ModuleType | None
                ) = await integration.async_get_platform("config")
                # Test if config platform has a config validator
                if not hasattr(config_platform, "async_validate_config"):
                    config_platform = None
            except ImportError:
                config_platform = None

            merge_list = False

            # If integration has a custom config validator, it needs to provide a hint.
            if config_platform is not None:
                merge_list = config_platform.PACKAGE_MERGE_HINT == "list"

            if not merge_list:
                merge_list = hasattr(component, "PLATFORM_SCHEMA")

            if not merge_list and hasattr(component, "CONFIG_SCHEMA"):
                merge_list = _identify_config_schema(component) == "list"

            if merge_list:
                config[comp_name] = cv.remove_falsy(
                    cv.ensure_list(config.get(comp_name)) + cv.ensure_list(comp_conf)
                )
                continue

            if comp_conf is None:
                comp_conf = OrderedDict()

            if not isinstance(comp_conf, dict):
                _log_pkg_error(
                    hass,
                    pack_name,
                    comp_name,
                    config,
                    f"integration '{comp_name}' cannot be merged, expected a dict",
                )
                continue

            if comp_name not in config or config[comp_name] is None:
                config[comp_name] = OrderedDict()

            if not isinstance(config[comp_name], dict):
                _log_pkg_error(
                    hass,
                    pack_name,
                    comp_name,
                    config,
                    (
                        f"integration '{comp_name}' cannot be merged, dict expected in "
                        "main config"
                    ),
                )
                continue

            duplicate_key = _recursive_merge(conf=config[comp_name], package=comp_conf)
            if duplicate_key:
                _log_pkg_error(
                    hass,
                    pack_name,
                    comp_name,
                    config,
                    f"integration '{comp_name}' has duplicate key '{duplicate_key}'",
                )

    for pack_name in invalid_packages:
        packages.pop(pack_name, {})

    return config


@callback
def _get_log_message_and_stack_print_pref(
    hass: HomeAssistant, domain: str, platform_exception: ConfigExceptionInfo
) -> tuple[str | None, bool, dict[str, str]]:
    """Get message to log and print stack trace preference."""
    exception = platform_exception.exception
    platform_path = platform_exception.platform_path
    platform_config = platform_exception.config
    link = platform_exception.integration_link

    placeholders: dict[str, str] = {
        "domain": domain,
        "error": str(exception),
        "p_name": platform_path,
    }

    show_stack_trace: bool | None = _CONFIG_LOG_SHOW_STACK_TRACE.get(
        platform_exception.translation_key
    )
    if show_stack_trace is None:
        # If no pre defined log_message is set, we generate an enriched error
        # message, so we can notify about it during setup
        show_stack_trace = False
        if isinstance(exception, vol.Invalid):
            log_message = format_schema_error(
                hass, exception, platform_path, platform_config, link
            )
            if annotation := find_annotation(platform_config, exception.path):
                placeholders["config_file"], line = annotation
                placeholders["line"] = str(line)
        else:
            if TYPE_CHECKING:
                assert isinstance(exception, HomeAssistantError)
            log_message = format_homeassistant_error(
                hass, exception, platform_path, platform_config, link
            )
            if annotation := find_annotation(platform_config, [platform_path]):
                placeholders["config_file"], line = annotation
                placeholders["line"] = str(line)
            show_stack_trace = True
        return (log_message, show_stack_trace, placeholders)

    # Generate the log message from the English translations
    log_message = async_get_exception_message(
        HOMEASSISTANT_DOMAIN,
        platform_exception.translation_key,
        translation_placeholders=placeholders,
    )

    return (log_message, show_stack_trace, placeholders)


async def async_process_component_and_handle_errors(
    hass: HomeAssistant,
    config: ConfigType,
    integration: Integration,
    raise_on_failure: bool = False,
) -> ConfigType | None:
    """Process and component configuration and handle errors.

    In case of errors:
    - Print the error messages to the log.
    - Raise a ConfigValidationError if raise_on_failure is set.

    Returns the integration config or `None`.
    """
    integration_config_info = await async_process_component_config(
        hass, config, integration
    )
    async_handle_component_errors(
        hass, integration_config_info, integration, raise_on_failure
    )
    return async_drop_config_annotations(integration_config_info, integration)


@callback
def async_drop_config_annotations(
    integration_config_info: IntegrationConfigInfo,
    integration: Integration,
) -> ConfigType | None:
    """Remove file and line annotations from str items in component configuration."""
    if (config := integration_config_info.config) is None:
        return None

    def drop_config_annotations_rec(node: Any) -> Any:
        if isinstance(node, dict):
            # Some integrations store metadata in custom dict classes, preserve those
            tmp = dict(node)
            node.clear()
            node.update(
                (drop_config_annotations_rec(k), drop_config_annotations_rec(v))
                for k, v in tmp.items()
            )
            return node

        if isinstance(node, list):
            return [drop_config_annotations_rec(v) for v in node]

        if isinstance(node, NodeStrClass):
            return str(node)

        return node

    # Don't drop annotations from the homeassistant integration because it may
    # have configuration for other integrations as packages.
    if integration.domain in config and integration.domain != HOMEASSISTANT_DOMAIN:
        drop_config_annotations_rec(config[integration.domain])
    return config


@callback
def async_handle_component_errors(
    hass: HomeAssistant,
    integration_config_info: IntegrationConfigInfo,
    integration: Integration,
    raise_on_failure: bool = False,
) -> None:
    """Handle component configuration errors from async_process_component_config.

    In case of errors:
    - Print the error messages to the log.
    - Raise a ConfigValidationError if raise_on_failure is set.
    """

    if not (config_exception_info := integration_config_info.exception_info_list):
        return

    platform_exception: ConfigExceptionInfo
    domain = integration.domain
    placeholders: dict[str, str]
    for platform_exception in config_exception_info:
        exception = platform_exception.exception
        (
            log_message,
            show_stack_trace,
            placeholders,
        ) = _get_log_message_and_stack_print_pref(hass, domain, platform_exception)
        _LOGGER.error(
            log_message,
            exc_info=exception if show_stack_trace else None,
        )

    if not raise_on_failure:
        return

    if len(config_exception_info) == 1:
        translation_key = platform_exception.translation_key
    else:
        translation_key = ConfigErrorTranslationKey.MULTIPLE_INTEGRATION_CONFIG_ERRORS
        errors = str(len(config_exception_info))
        placeholders = {
            "domain": domain,
            "errors": errors,
        }
    raise ConfigValidationError(
        translation_key,
        [platform_exception.exception for platform_exception in config_exception_info],
        translation_domain=HOMEASSISTANT_DOMAIN,
        translation_placeholders=placeholders,
    )


def config_per_platform(
    config: ConfigType, domain: str
) -> Iterable[tuple[str | None, ConfigType]]:
    """Break a component config into different platforms.

    For example, will find 'switch', 'switch 2', 'switch 3', .. etc
    Async friendly.
    """
    for config_key in extract_domain_configs(config, domain):
        if not (platform_config := config[config_key]):
            continue

        if not isinstance(platform_config, list):
            platform_config = [platform_config]

        item: ConfigType
        platform: str | None
        for item in platform_config:
            try:
                platform = item.get(CONF_PLATFORM)
            except AttributeError:
                platform = None

            yield platform, item


def extract_platform_integrations(
    config: ConfigType, domains: set[str]
) -> dict[str, set[str]]:
    """Find all the platforms in a configuration.

    Returns a dictionary with domain as key and a set of platforms as value.
    """
    platform_integrations: dict[str, set[str]] = {}
    for key, domain_config in config.items():
        try:
            domain = cv.domain_key(key)
        except vol.Invalid:
            continue
        if domain not in domains:
            continue

        if not isinstance(domain_config, list):
            domain_config = [domain_config]

        for item in domain_config:
            try:
                platform = item.get(CONF_PLATFORM)
            except AttributeError:
                continue
            if platform and isinstance(platform, Hashable):
                platform_integrations.setdefault(domain, set()).add(platform)
    return platform_integrations


def extract_domain_configs(config: ConfigType, domain: str) -> Sequence[str]:
    """Extract keys from config for given domain name.

    Async friendly.
    """
    domain_configs = []
    for key in config:
        with suppress(vol.Invalid):
            if cv.domain_key(key) != domain:
                continue
            domain_configs.append(key)
    return domain_configs


@dataclass(slots=True)
class _PlatformIntegration:
    """Class to hold platform integration information."""

    path: str  # integration.platform; ex: filter.sensor
    name: str  # integration; ex: filter
    integration: Integration  # <Integration filter>
    config: ConfigType  # un-validated config
    validated_config: ConfigType  # component validated config


async def _async_load_and_validate_platform_integration(
    domain: str,
    integration_docs: str | None,
    config_exceptions: list[ConfigExceptionInfo],
    p_integration: _PlatformIntegration,
) -> ConfigType | None:
    """Load a platform integration and validate its config."""
    try:
        platform = await p_integration.integration.async_get_platform(domain)
    except LOAD_EXCEPTIONS as exc:
        exc_info = ConfigExceptionInfo(
            exc,
            ConfigErrorTranslationKey.PLATFORM_COMPONENT_LOAD_EXC,
            p_integration.path,
            p_integration.config,
            integration_docs,
        )
        config_exceptions.append(exc_info)
        return None

    # If the platform does not have a config schema
    # the top level component validated schema will be used
    if not hasattr(platform, "PLATFORM_SCHEMA"):
        return p_integration.validated_config

    # Validate platform specific schema
    try:
        return platform.PLATFORM_SCHEMA(p_integration.config)  # type: ignore[no-any-return]
    except vol.Invalid as exc:
        exc_info = ConfigExceptionInfo(
            exc,
            ConfigErrorTranslationKey.PLATFORM_CONFIG_VALIDATION_ERR,
            p_integration.path,
            p_integration.config,
            p_integration.integration.documentation,
        )
        config_exceptions.append(exc_info)
    except Exception as exc:  # noqa: BLE001
        exc_info = ConfigExceptionInfo(
            exc,
            ConfigErrorTranslationKey.PLATFORM_SCHEMA_VALIDATOR_ERR,
            p_integration.name,
            p_integration.config,
            p_integration.integration.documentation,
        )
        config_exceptions.append(exc_info)

    return None


async def async_process_component_config(
    hass: HomeAssistant,
    config: ConfigType,
    integration: Integration,
    component: ComponentProtocol | None = None,
) -> IntegrationConfigInfo:
    """Check component configuration.

    Returns processed configuration and exception information.

    This method must be run in the event loop.
    """
    domain = integration.domain
    integration_docs = integration.documentation
    config_exceptions: list[ConfigExceptionInfo] = []

    if not component:
        try:
            component = await integration.async_get_component()
        except LOAD_EXCEPTIONS as exc:
            exc_info = ConfigExceptionInfo(
                exc,
                ConfigErrorTranslationKey.COMPONENT_IMPORT_ERR,
                domain,
                config,
                integration_docs,
            )
            config_exceptions.append(exc_info)
            return IntegrationConfigInfo(None, config_exceptions)

    # Check if the integration has a custom config validator
    config_validator = None
    # A successful call to async_get_component will prime
    # the cache for platforms_exists to ensure it does no
    # blocking I/O
    if integration.platforms_exists(("config",)):
        # If the config platform cannot possibly exist, don't try to load it.
        try:
            config_validator = await integration.async_get_platform("config")
        except ImportError as err:
            # Filter out import error of the config platform.
            # If the config platform contains bad imports, make sure
            # that still fails.
            if err.name != f"{integration.pkg_path}.config":
                exc_info = ConfigExceptionInfo(
                    err,
                    ConfigErrorTranslationKey.CONFIG_PLATFORM_IMPORT_ERR,
                    domain,
                    config,
                    integration_docs,
                )
                config_exceptions.append(exc_info)
                return IntegrationConfigInfo(None, config_exceptions)

    if config_validator is not None and hasattr(
        config_validator, "async_validate_config"
    ):
        try:
            return IntegrationConfigInfo(
                await config_validator.async_validate_config(hass, config), []
            )
        except (vol.Invalid, HomeAssistantError) as exc:
            exc_info = ConfigExceptionInfo(
                exc,
                ConfigErrorTranslationKey.CONFIG_VALIDATION_ERR,
                domain,
                config,
                integration_docs,
            )
            config_exceptions.append(exc_info)
            return IntegrationConfigInfo(None, config_exceptions)
        except Exception as exc:  # noqa: BLE001
            exc_info = ConfigExceptionInfo(
                exc,
                ConfigErrorTranslationKey.CONFIG_VALIDATOR_UNKNOWN_ERR,
                domain,
                config,
                integration_docs,
            )
            config_exceptions.append(exc_info)
            return IntegrationConfigInfo(None, config_exceptions)

    # No custom config validator, proceed with schema validation
    if hasattr(component, "CONFIG_SCHEMA"):
        try:
            return IntegrationConfigInfo(
                await cv.async_validate(hass, component.CONFIG_SCHEMA, config), []
            )
        except vol.Invalid as exc:
            exc_info = ConfigExceptionInfo(
                exc,
                ConfigErrorTranslationKey.CONFIG_VALIDATION_ERR,
                domain,
                config,
                integration_docs,
            )
            config_exceptions.append(exc_info)
            return IntegrationConfigInfo(None, config_exceptions)
        except Exception as exc:  # noqa: BLE001
            exc_info = ConfigExceptionInfo(
                exc,
                ConfigErrorTranslationKey.CONFIG_SCHEMA_UNKNOWN_ERR,
                domain,
                config,
                integration_docs,
            )
            config_exceptions.append(exc_info)
            return IntegrationConfigInfo(None, config_exceptions)

    component_platform_schema = getattr(
        component, "PLATFORM_SCHEMA_BASE", getattr(component, "PLATFORM_SCHEMA", None)
    )

    if component_platform_schema is None:
        return IntegrationConfigInfo(config, [])

    platform_integrations_to_load: list[_PlatformIntegration] = []
    platforms: list[ConfigType] = []
    for p_name, p_config in config_per_platform(config, domain):
        # Validate component specific platform schema
        platform_path = f"{p_name}.{domain}"
        try:
            p_validated = await cv.async_validate(
                hass, component_platform_schema, p_config
            )
        except vol.Invalid as exc:
            exc_info = ConfigExceptionInfo(
                exc,
                ConfigErrorTranslationKey.PLATFORM_CONFIG_VALIDATION_ERR,
                domain,
                p_config,
                integration_docs,
            )
            config_exceptions.append(exc_info)
            continue
        except Exception as exc:  # noqa: BLE001
            exc_info = ConfigExceptionInfo(
                exc,
                ConfigErrorTranslationKey.PLATFORM_SCHEMA_VALIDATOR_ERR,
                str(p_name),
                config,
                integration_docs,
            )
            config_exceptions.append(exc_info)
            continue

        # Not all platform components follow same pattern for platforms
        # So if p_name is None we are not going to validate platform
        # (the automation component is one of them)
        if p_name is None:
            platforms.append(p_validated)
            continue

        try:
            p_integration = await async_get_integration_with_requirements(hass, p_name)
        except (RequirementsNotFound, IntegrationNotFound) as exc:
            exc_info = ConfigExceptionInfo(
                exc,
                ConfigErrorTranslationKey.PLATFORM_COMPONENT_LOAD_ERR,
                platform_path,
                p_config,
                integration_docs,
            )
            config_exceptions.append(exc_info)
            continue

        platform_integration = _PlatformIntegration(
            platform_path, p_name, p_integration, p_config, p_validated
        )
        platform_integrations_to_load.append(platform_integration)

    #
    # Since bootstrap will order base platform (ie sensor) integrations
    # first, we eagerly gather importing the platforms that need to be
    # validated for the base platform since everything that uses the
    # base platform has to wait for it to finish.
    #
    # For example if `hue` where to load first and than called
    # `async_forward_entry_setup` for the `sensor` platform it would have to
    # wait for the sensor platform to finish loading before it could continue.
    # Since the base `sensor` platform must also import all of its platform
    # integrations to do validation before it can finish setup, its important
    # that the platform integrations are imported first so we do not waste
    # time importing `hue` first when we could have been importing the platforms
    # that the base `sensor` platform need to load to do validation and allow
    # all integrations that need the base `sensor` platform to proceed with setup.
    #
    if platform_integrations_to_load:
        async_load_and_validate = partial(
            _async_load_and_validate_platform_integration,
            domain,
            integration_docs,
            config_exceptions,
        )
        platforms.extend(
            validated_config
            for validated_config in await asyncio.gather(
                *(
                    create_eager_task(
                        async_load_and_validate(p_integration), loop=hass.loop
                    )
                    for p_integration in platform_integrations_to_load
                )
            )
            if validated_config is not None
        )

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, domain)
    config[domain] = platforms

    return IntegrationConfigInfo(config, config_exceptions)


@callback
def config_without_domain(config: ConfigType, domain: str) -> ConfigType:
    """Return a config with all configuration for a domain removed."""
    filter_keys = extract_domain_configs(config, domain)
    return {key: value for key, value in config.items() if key not in filter_keys}


async def async_check_ha_config_file(hass: HomeAssistant) -> str | None:
    """Check if Home Assistant configuration file is valid.

    This method is a coroutine.
    """
    # pylint: disable-next=import-outside-toplevel
    from .helpers import check_config

    res = await check_config.async_check_ha_config_file(hass)

    if not res.errors:
        return None
    return res.error_str


def safe_mode_enabled(config_dir: str) -> bool:
    """Return if safe mode is enabled.

    If safe mode is enabled, the safe mode file will be removed.
    """
    safe_mode_path = os.path.join(config_dir, SAFE_MODE_FILENAME)
    safe_mode = os.path.exists(safe_mode_path)
    if safe_mode:
        os.remove(safe_mode_path)
    return safe_mode


async def async_enable_safe_mode(hass: HomeAssistant) -> None:
    """Enable safe mode."""

    def _enable_safe_mode() -> None:
        Path(hass.config.path(SAFE_MODE_FILENAME)).touch()

    await hass.async_add_executor_job(_enable_safe_mode)
