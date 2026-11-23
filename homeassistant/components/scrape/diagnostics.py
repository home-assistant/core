"""Diagnostics support for Scrape."""

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_HEADERS, CONF_PASSWORD, CONF_PAYLOAD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import ScrapeConfigEntry
from .const import CONF_ADDITIONAL

TO_REDACT = {CONF_PASSWORD, CONF_PAYLOAD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ScrapeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    options = async_redact_data(entry.options, TO_REDACT)
    # Header values can hold tokens, the header names help to debug
    if headers := options.get(CONF_ADDITIONAL, {}).get(CONF_HEADERS):
        options[CONF_ADDITIONAL][CONF_HEADERS] = dict.fromkeys(headers, REDACTED)

    return {
        "options": options,
        "sensors": [
            {"title": subentry.title, "data": dict(subentry.data)}
            for subentry in entry.subentries.values()
        ],
        "last_update_success": coordinator.last_update_success,
        "data_fetched": coordinator.data is not None,
    }
