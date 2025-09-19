"""Diagnostics support for Satel Integra."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

TO_REDACT = {CONF_CODE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    diag: dict[str, Any] = {}

    diag["config_entry_data"] = dict(entry.data)
    diag["config_entry_options"] = async_redact_data(entry.options, TO_REDACT)

    diag["subentries"] = dict(entry.subentries)

    registry = er.async_get(hass)
    entities = registry.entities.get_entries_for_config_entry_id(entry.entry_id)

    diag["entities"] = [entity.extended_dict for entity in entities]

    return diag
