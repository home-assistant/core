"""Diagnostics platform for Habitica integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from .const import CONF_API_USER
from .types import HabiticaConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: HabiticaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    habitica_data = await config_entry.runtime_data.habitica.get_user_anonymized()

    return {
        "config_entry_data": {
            CONF_URL: config_entry.data[CONF_URL],
            CONF_API_USER: config_entry.data[CONF_API_USER],
        },
        "habitica_data": habitica_data.to_dict()["data"],
    }
