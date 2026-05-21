"""Diagnostics support for Virtual Remote."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
)

TO_REDACT = {"device_id", "unique_id", "uuid"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    remotes = _diagnostic_remotes(hass, entry)

    return {
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
        "virtual_remotes": remotes,
        "summary": {
            "remote_count": len(remotes),
            "command_count": sum(remote["command_count"] for remote in remotes),
            "missing_infrared_entity_count": sum(
                1 for remote in remotes if not remote["infrared_entity_exists"]
            ),
        },
    }


def _redacted_options(options: Mapping[str, Any]) -> dict[str, Any]:
    """Return options without full infrared command payloads."""
    redacted = dict(options)
    remotes = redacted.get(CONF_VIRTUAL_REMOTES)
    if not isinstance(remotes, list):
        return redacted

    redacted_remotes: list[dict[str, Any]] = []
    for item in remotes:
        if not isinstance(item, dict):
            continue

        remote = dict(item)
        commands = remote.get(CONF_REMOTE_COMMANDS, {})
        if isinstance(commands, dict):
            remote[CONF_REMOTE_COMMANDS] = sorted(commands)
        redacted_remotes.append(remote)

    redacted[CONF_VIRTUAL_REMOTES] = redacted_remotes
    return redacted


def _diagnostic_remotes(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> list[dict[str, Any]]:
    """Return sanitized virtual remote diagnostics."""
    remotes = entry.options.get(CONF_VIRTUAL_REMOTES, [])
    if not isinstance(remotes, list):
        return []

    diagnostics: list[dict[str, Any]] = []
    for item in remotes:
        if not isinstance(item, dict):
            continue

        infrared_entity_id = item.get(CONF_INFRARED_ENTITY_ID)
        commands = item.get(CONF_REMOTE_COMMANDS, {})
        diagnostics.append(
            {
                "id": item.get(CONF_REMOTE_ID),
                "name": item.get(CONF_REMOTE_NAME),
                "infrared_entity_id": infrared_entity_id,
                "infrared_entity_exists": (
                    isinstance(infrared_entity_id, str)
                    and hass.states.get(infrared_entity_id) is not None
                ),
                "command_count": len(commands) if isinstance(commands, dict) else 0,
                "commands": sorted(commands) if isinstance(commands, dict) else [],
            }
        )

    return diagnostics
