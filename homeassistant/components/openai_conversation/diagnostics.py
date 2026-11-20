"""Diagnostics support for OpenAI Conversation."""

from typing import Any

from openai import __title__, __version__

from homeassistant.const import CONF_PROMPT
from homeassistant.core import HomeAssistant

from . import OpenAIConfigEntry
from .const import (
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
)

TO_OMIT = {
    CONF_PROMPT,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OpenAIConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "client": f"{__title__}=={__version__}",
        "entry_version": f"{entry.version}.{entry.minor_version}",
        "state": entry.state.value,
        "subentries": [
            {
                "title": subentry.title,
                "subentry_type": subentry.subentry_type,
                "data": {
                    key: value
                    for key, value in subentry.data.items()
                    if key not in TO_OMIT
                },
            }
            for subentry in entry.subentries.values()
        ],
    }
