"""Diagnostics support for generic (IP camera)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data, redact_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_STILL_IMAGE_URL, CONF_STREAM_SOURCE

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    options = async_redact_data(entry.options, TO_REDACT)
    for key in (CONF_STREAM_SOURCE, CONF_STILL_IMAGE_URL):
        if (value := options.get(key)) is not None:
            options[key] = redact_url(value)

    return {
        "title": entry.title,
        "data": async_redact_data(entry.data, TO_REDACT),
        "options": options,
    }
