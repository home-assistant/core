"""Diagnostics for MELCloud Home integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .coordinator import MelCloudHomeConfigEntry

TO_REDACT = [
    CONF_EMAIL,
    CONF_PASSWORD,
    "first_name",
    "last_name",
    "title",
    CONF_UNIQUE_ID,
    "id",
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MelCloudHomeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a MELCloud Home config entry."""

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "coordinator": async_redact_data(
            config_entry.runtime_data.data.model_dump(mode="json"), TO_REDACT
        ),
    }
