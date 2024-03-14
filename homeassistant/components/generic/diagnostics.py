"""Diagnostics support for generic (IP camera)."""

from __future__ import annotations

from typing import Any

import yarl

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_STILL_IMAGE_URL, CONF_STREAM_SOURCE

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
}


# A very similar redact function is in components.sql.  Possible to be made common.
def redact_url(data: str) -> str:
    """Redact credentials from string url."""
    url = url_in = yarl.URL(data)
    if url_in.user:
        url = url.with_user("****")
    if url_in.password:
        url = url.with_password("****")
    if url_in.path != "/":
        url = url.with_path("****")
    if url_in.query_string:
        url = url.with_query("****=****")
    return str(url)


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
