"""Diagnostics platform for SMTP integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import SmtpConfigEntry
from .const import CONF_REPLY_TO, CONF_REPLY_TO_NAME, CONF_SENDER_NAME, CONF_SERVER

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_SENDER,
    CONF_SENDER_NAME,
    CONF_REPLY_TO,
    CONF_REPLY_TO_NAME,
    CONF_SERVER,
    CONF_RECIPIENT,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: SmtpConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "data": async_redact_data(data=config_entry.data, to_redact=TO_REDACT),
        "options": async_redact_data(data=config_entry.options, to_redact=TO_REDACT),
        "subentries": len(config_entry.subentries),
    }
