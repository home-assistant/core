"""Helpers for automation."""

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS

from .typing import ConfigType


def get_absolute_description_key(domain: str, key: str) -> str:
    """Return the absolute description key."""
    if not key.startswith("_"):
        return f"{domain}.{key}"
    key = key[1:]  # Remove leading underscore
    if not key:
        return domain
    return key


def get_relative_description_key(domain: str, key: str) -> str:
    """Return the relative description key."""
    platform, *subtype = key.split(".", 1)
    if platform != domain:
        return f"_{key}"
    if not subtype:
        return "_"
    return subtype[0]


def move_top_level_schema_fields_to_options(
    config: ConfigType, options_schema_dict: dict[vol.Marker, Any]
) -> ConfigType:
    """Move top-level fields to options.

    This function is used to help migrating old-style configs to new-style configs
    for triggers and conditions.
    If options is already present, the config is returned as-is.
    """
    if CONF_OPTIONS in config:
        return config

    config = config.copy()
    options = config.setdefault(CONF_OPTIONS, {})

    # Move top-level fields to options
    for key_marked in options_schema_dict:
        key = key_marked.schema
        if key in config:
            options[key] = config.pop(key)

    return config


def move_options_fields_to_top_level(
    config: ConfigType, base_schema: vol.Schema
) -> ConfigType:
    """Move options fields to top-level.

    This function is used to provide backwards compatibility for new-style configs
    for triggers and conditions.

    The config is returned as-is, if any of the following is true:
    - options is not present
    - options is not a dict
    - the config with options field removed fails the base_schema validation (most
    likely due to additional keys being present)

    Those conditions are checked to make it so that only configs that have the structure
    of the new-style are modified, whereas valid old-style configs are preserved.
    """
    options = config.get(CONF_OPTIONS)

    if not isinstance(options, dict):
        return config

    new_config: ConfigType = config.copy()
    new_config.pop(CONF_OPTIONS)

    try:
        new_config = base_schema(new_config)
    except vol.Invalid:
        return config

    new_config.update(options)

    return new_config
