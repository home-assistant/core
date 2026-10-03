"""Helper functions for the Virtual Remote integration."""

from collections.abc import Mapping
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
)

_REMOTE_ID_RE = re.compile(r"[^a-z0-9_]+")
_COMMAND_NAME_RE = re.compile(r"[^A-Z0-9_]+")


def available_infrared_entities(
    hass: HomeAssistant,
) -> dict[str, selector.SelectOptionDict]:
    """Return available infrared entities.

    Multiple virtual remotes may use the same infrared transmitter because one
    physical IR output can control multiple appliances, for example through
    dual emitters or a blaster.
    """
    registry = er.async_get(hass)
    options: dict[str, selector.SelectOptionDict] = {}

    for registry_entry in registry.entities.values():
        if (
            registry_entry.domain != "infrared"
            or registry_entry.disabled_by is not None
        ):
            continue

        entity_id = registry_entry.entity_id
        label = (
            registry_entry.name
            or registry_entry.original_name
            or registry_entry.entity_id
        )
        options[entity_id] = selector.SelectOptionDict(
            value=entity_id,
            label=label,
        )

    return dict(sorted(options.items()))


def infrared_entity_selector(
    available_entities: dict[str, selector.SelectOptionDict],
    *,
    current_entity_id: str | None = None,
) -> selector.SelectSelector:
    """Return an infrared entity selector."""
    options = dict(available_entities)

    if current_entity_id and current_entity_id not in options:
        options[current_entity_id] = selector.SelectOptionDict(
            value=current_entity_id,
            label=f"{current_entity_id} (unavailable)",
        )

    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(options.values()),
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def infrared_entity_field(
    default_entity_id: str,
    available_entities: dict[str, selector.SelectOptionDict],
) -> vol.Required:
    """Return a required infrared entity field with a valid default if possible."""
    if default_entity_id and default_entity_id in available_entities:
        return vol.Required(CONF_INFRARED_ENTITY_ID, default=default_entity_id)

    return vol.Required(CONF_INFRARED_ENTITY_ID)


def infrared_entity_field_with_current(
    default_entity_id: str,
    _available_entities: dict[str, selector.SelectOptionDict],
) -> vol.Required:
    """Return an infrared entity field allowing a stale current entity default."""
    if default_entity_id:
        return vol.Required(CONF_INFRARED_ENTITY_ID, default=default_entity_id)

    return vol.Required(CONF_INFRARED_ENTITY_ID)


def normalize_remote_id(name: str) -> str:
    """Create a stable id from a remote name."""
    value = name.strip().casefold().replace(" ", "_")
    value = _REMOTE_ID_RE.sub("_", value)
    value = value.strip("_")
    return value or "remote"


def unique_remote_id(
    name: str,
    remotes: list[dict[str, Any]],
    *,
    current_remote_id: str | None = None,
) -> str:
    """Create a remote id which is unique among configured remotes."""
    remote_id = normalize_remote_id(name)
    existing_ids = {
        str(remote.get(CONF_REMOTE_ID))
        for remote in remotes
        if remote.get(CONF_REMOTE_ID) != current_remote_id
    }

    if remote_id not in existing_ids:
        return remote_id

    counter = 2
    while f"{remote_id}_{counter}" in existing_ids:
        counter += 1

    return f"{remote_id}_{counter}"


def normalize_command_name(name: str) -> str:
    """Normalize a user-provided command name."""
    value = name.strip().upper().replace(" ", "_")
    value = _COMMAND_NAME_RE.sub("_", value)
    return value.strip("_")


def find_command_key(
    commands: Mapping[str, Any],
    normalized_command_name: str,
) -> str | None:
    """Return the existing command key matching a normalized command name."""
    return next(
        (
            command_name
            for command_name in commands
            if normalize_command_name(str(command_name)) == normalized_command_name
        ),
        None,
    )


def virtual_remote_from_config_entry_data(
    value: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return a normalized single virtual remote definition from config entry data."""
    remote_id = value.get(CONF_REMOTE_ID)
    name = value.get(CONF_REMOTE_NAME)
    infrared_entity_id = value.get(CONF_INFRARED_ENTITY_ID)

    if (
        not isinstance(remote_id, str)
        or not remote_id
        or not isinstance(name, str)
        or not name
        or not isinstance(infrared_entity_id, str)
        or not infrared_entity_id
    ):
        return None

    remote: dict[str, Any] = {
        CONF_REMOTE_ID: remote_id,
        CONF_REMOTE_NAME: name,
        CONF_INFRARED_ENTITY_ID: infrared_entity_id,
    }

    commands = _normalize_command_mapping(value.get(CONF_REMOTE_COMMANDS, {}))
    if commands:
        remote[CONF_REMOTE_COMMANDS] = commands

    return remote


def virtual_remotes_from_config_entry(entry: ConfigEntry) -> list[dict[str, Any]]:
    """Return virtual remote definitions from current or single-entry storage.

    The standalone Virtual Remote integration is moving toward one virtual
    remote per config entry. The shared remote entity setup still consumes a
    list so it can also support integrations, such as iTach IP2IR, where one
    hardware config entry owns multiple virtual remotes.
    """
    remotes = normalize_virtual_remotes(entry.options.get(CONF_VIRTUAL_REMOTES))
    if remotes:
        return remotes

    remotes = normalize_virtual_remotes(entry.data.get(CONF_VIRTUAL_REMOTES))
    if remotes:
        return remotes

    single_remote = virtual_remote_from_config_entry_data(
        {
            **entry.data,
            **entry.options,
        }
    )
    return [single_remote] if single_remote is not None else []


def normalize_virtual_remotes(value: Any) -> list[dict[str, Any]]:
    """Return normalized virtual remote definitions from stored options."""
    if not isinstance(value, list):
        return []

    remotes: list[dict[str, Any]] = []
    seen_remote_ids: set[str] = set()

    for item in value:
        if not isinstance(item, Mapping):
            continue

        remote_id = item.get(CONF_REMOTE_ID)
        name = item.get(CONF_REMOTE_NAME)
        infrared_entity_id = item.get(CONF_INFRARED_ENTITY_ID)

        if (
            not isinstance(remote_id, str)
            or not remote_id
            or not isinstance(name, str)
            or not name
            or not isinstance(infrared_entity_id, str)
            or not infrared_entity_id
            or remote_id in seen_remote_ids
        ):
            continue

        remote: dict[str, Any] = {
            CONF_REMOTE_ID: remote_id,
            CONF_REMOTE_NAME: name,
            CONF_INFRARED_ENTITY_ID: infrared_entity_id,
        }

        commands = _normalize_command_mapping(item.get(CONF_REMOTE_COMMANDS, {}))
        if commands:
            remote[CONF_REMOTE_COMMANDS] = commands

        remotes.append(remote)
        seen_remote_ids.add(remote_id)

    return remotes


def remotes_with_commands(remotes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return remotes which have at least one named command."""
    return [
        remote
        for remote in remotes
        if _normalize_command_mapping(remote.get(CONF_REMOTE_COMMANDS, {}))
    ]


def command_options(commands: Mapping[str, Any]) -> list[selector.SelectOptionDict]:
    """Return selector options for command names."""
    return [
        selector.SelectOptionDict(value=command_name, label=command_name)
        for command_name in sorted(_normalize_command_mapping(commands))
    ]


def remote_options(remotes: list[dict[str, Any]]) -> list[selector.SelectOptionDict]:
    """Return selector options for remotes."""
    return [
        selector.SelectOptionDict(
            value=str(remote[CONF_REMOTE_ID]),
            label=str(remote[CONF_REMOTE_NAME]),
        )
        for remote in remotes
    ]


def _normalize_command_mapping(value: Any) -> dict[str, str]:
    """Return a normalized command mapping."""
    if not isinstance(value, Mapping):
        return {}

    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and key and isinstance(item, str)
    }
