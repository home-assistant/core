"""Diagnostics platform for Telegram bot integration."""

from __future__ import annotations

from typing import Any

from yarl import URL

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from . import TelegramBotConfigEntry
from .const import CONF_CHAT_ID

TO_REDACT = [CONF_API_KEY, CONF_CHAT_ID]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: TelegramBotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data = async_redact_data(config_entry.data, TO_REDACT)
    if config_entry.data.get(CONF_URL):
        url = URL(config_entry.data[CONF_URL])
        data[CONF_URL] = url.with_host(REDACTED).human_repr()

    return {
        "data": data,
        "options": async_redact_data(config_entry.options, TO_REDACT),
        "subentries": [
            async_redact_data(subentry.data, TO_REDACT)
            for subentry in config_entry.subentries.values()
        ],
    }
