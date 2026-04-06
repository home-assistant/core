"""Diagnostics support for Anthropic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from anthropic import __title__, __version__

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_PROMPT,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import AnthropicConfigEntry


TO_REDACT = {
    CONF_API_KEY,
    CONF_PROMPT,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_TIMEZONE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AnthropicConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "client": f"{__title__}=={__version__}",
        "title": entry.title,
        "entry_id": entry.entry_id,
        "entry_version": f"{entry.version}.{entry.minor_version}",
        "state": entry.state.value,
        "data": async_redact_data(entry.data, TO_REDACT),
        "options": async_redact_data(entry.options, TO_REDACT),
        "subentries": {
            subentry.subentry_id: {
                "title": subentry.title,
                "subentry_type": subentry.subentry_type,
                "data": async_redact_data(subentry.data, TO_REDACT),
            }
            for subentry in entry.subentries.values()
        },
        "entities": {
            entity_entry.entity_id: entity_entry.extended_dict
            for entity_entry in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
        },
    }
