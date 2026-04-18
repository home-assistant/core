"""Diagnostics platform for Telegram bot integration."""

from __future__ import annotations

from typing import Any

from yarl import URL

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from . import TelegramBotConfigEntry
from .const import CONF_API_ENDPOINT, CONF_CHAT_ID, DEFAULT_API_ENDPOINT

TO_REDACT = [CONF_API_KEY, CONF_CHAT_ID]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: TelegramBotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data = async_redact_data(config_entry.data, TO_REDACT)
    if config_entry.data.get(CONF_URL):
        url = URL(config_entry.data[CONF_URL])
        data[CONF_URL] = url.with_host(REDACTED).human_repr()

    api_endpoint = config_entry.data.get(CONF_API_ENDPOINT)
    if api_endpoint and api_endpoint != DEFAULT_API_ENDPOINT:
        url = URL(config_entry.data[CONF_API_ENDPOINT])
        data[CONF_API_ENDPOINT] = url.with_host(REDACTED).human_repr()

    return {
        "data": data,
        "options": async_redact_data(config_entry.options, TO_REDACT),
        "subentries_count": len(config_entry.subentries.values()),
    }
