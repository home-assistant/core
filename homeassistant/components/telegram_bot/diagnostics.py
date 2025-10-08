"""Diagnostics platform for Telegram bot integration."""

from __future__ import annotations

from typing import Any

from yarl import URL

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from . import TelegramBotConfigEntry
from .const import CONF_CHAT_ID


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: TelegramBotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data = dict(config_entry.data)
    data[CONF_API_KEY] = REDACTED

    if config_entry.data.get(CONF_URL):
        url = URL(config_entry.data[CONF_URL])
        data[CONF_URL] = url.with_host(REDACTED).human_repr()

    subentries = []
    for subentry in config_entry.subentries.values():
        subentry_data = dict(subentry.data)
        subentry_data[CONF_CHAT_ID] = REDACTED
        subentries.append(subentry_data)

    return {
        "data": data,
        "options": dict(config_entry.options),
        "subentries": subentries,
    }
