"""Diagnostics support for OneDrive."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_DELETE_PERMANENTLY, CONF_FOLDER_ID, CONF_FOLDER_NAME
from .coordinator import OneDriveConfigEntry

TO_REDACT = {"display_name", "email"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: OneDriveConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data.coordinator

    data = {
        "drive": asdict(coordinator.data),
        "config": {
            # use gets to avoid errors with migration failures
            CONF_FOLDER_NAME: entry.data.get(CONF_FOLDER_NAME),
            CONF_FOLDER_ID: entry.data.get(CONF_FOLDER_ID),
            CONF_DELETE_PERMANENTLY: entry.options.get(CONF_DELETE_PERMANENTLY, False),
        },
    }

    return async_redact_data(data, TO_REDACT)
