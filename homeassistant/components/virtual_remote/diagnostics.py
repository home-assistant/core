"""Diagnostics support for Virtual Remote."""

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
)
from .helpers import virtual_remotes_from_config_entry

TO_REDACT = {"device_id", "unique_id", "uuid"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    remote_diagnostics = _diagnostic_remotes(hass, entry)

    diagnostics_data: dict[str, Any] = {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "domain": entry.domain,
                "data": dict(entry.data),
                "options": _redacted_options(entry.options),
                "unique_id": entry.unique_id,
            },
            TO_REDACT,
        ),
        "summary": {
            "remote_count": len(remote_diagnostics),
            "command_count": sum(
                remote["command_count"] for remote in remote_diagnostics
            ),
            "missing_infrared_entity_count": sum(
                1
                for remote in remote_diagnostics
                if not remote["infrared_entity_exists"]
            ),
        },
    }

    if CONF_REMOTE_ID in entry.data:
        diagnostics_data["virtual_remote"] = (
            remote_diagnostics[0] if remote_diagnostics else None
        )
    else:
        diagnostics_data["virtual_remotes"] = remote_diagnostics

    return diagnostics_data


def _redacted_options(options: Mapping[str, Any]) -> dict[str, Any]:
    """Return options without full infrared command payloads."""
    redacted = dict(options)

    commands = redacted.get(CONF_REMOTE_COMMANDS)
    if isinstance(commands, dict):
        redacted[CONF_REMOTE_COMMANDS] = sorted(commands)

    remotes = redacted.get(CONF_VIRTUAL_REMOTES)
    if not isinstance(remotes, list):
        return redacted

    redacted_remotes: list[dict[str, Any]] = []
    for item in remotes:
        if not isinstance(item, dict):
            continue

        remote = dict(item)
        remote_commands = remote.get(CONF_REMOTE_COMMANDS, {})
        if isinstance(remote_commands, dict):
            remote[CONF_REMOTE_COMMANDS] = sorted(remote_commands)
        redacted_remotes.append(remote)

    redacted[CONF_VIRTUAL_REMOTES] = redacted_remotes
    return redacted


def _diagnostic_remotes(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> list[dict[str, Any]]:
    """Return sanitized virtual remote diagnostics."""
    diagnostics: list[dict[str, Any]] = []
    for item in virtual_remotes_from_config_entry(entry):
        infrared_entity_id = item.get(CONF_INFRARED_ENTITY_ID)
        commands = item.get(CONF_REMOTE_COMMANDS, {})
        diagnostics.append(
            {
                "id": item.get(CONF_REMOTE_ID),
                "name": item.get(CONF_REMOTE_NAME),
                "infrared_entity_id": infrared_entity_id,
                "infrared_entity_exists": (
                    isinstance(infrared_entity_id, str)
                    and (state := hass.states.get(infrared_entity_id)) is not None
                    and state.state != STATE_UNAVAILABLE
                ),
                "command_count": len(commands) if isinstance(commands, dict) else 0,
                "commands": sorted(commands) if isinstance(commands, dict) else [],
            }
        )

    return diagnostics
