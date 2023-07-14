"""Diagnostics support for Hue."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SECURE_DEVICES_PIN, CONF_SERVICE_ACCOUNT, DATA_CONFIG, DOMAIN
from .http import GoogleConfig
from .smart_home import (
    async_devices_query_response,
    async_devices_sync_response,
    create_sync_response,
)

TO_REDACT = [
    "uuid",
    "baseUrl",
    "webhookId",
    CONF_SERVICE_ACCOUNT,
    CONF_SECURE_DEVICES_PIN,
    CONF_API_KEY,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostic information."""
    data = hass.data[DOMAIN]
    config: GoogleConfig = data[entry.entry_id]
    yaml_config: ConfigType = data[DATA_CONFIG]
    devices = await async_devices_sync_response(hass, config, REDACTED)
    sync = create_sync_response(REDACTED, devices)
    query = await async_devices_query_response(hass, config, devices)

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "yaml_config": async_redact_data(yaml_config, TO_REDACT),
        "sync": async_redact_data(sync, TO_REDACT),
        "query": async_redact_data(query, TO_REDACT),
    }
