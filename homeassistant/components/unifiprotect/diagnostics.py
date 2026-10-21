"""Diagnostics support for UniFi Network."""

from typing import Any

from uiprotect.anonymize import anonymize_data

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .data import UFPConfigEntry

# Stream URLs carry the console host and a secret alias.
TO_REDACT = {"rtspsStreams"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: UFPConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    api = config_entry.runtime_data.api
    diagnostics: dict[str, Any] = {"options": dict(config_entry.options)}
    if not api.is_public_only:
        diagnostics["bootstrap"] = anonymize_data(api.bootstrap.unifi_dict())
    if api.has_public_bootstrap:
        diagnostics["public_bootstrap"] = async_redact_data(
            api.public_bootstrap.to_diagnostics(), TO_REDACT
        )
    return diagnostics
