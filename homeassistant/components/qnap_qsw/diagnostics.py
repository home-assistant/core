"""Support for the QNAP QSW diagnostics."""

from __future__ import annotations

from typing import Any

from aioqsw.const import QSD_MAC, QSD_SERIAL

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import QnapQswConfigEntry

TO_REDACT_CONFIG = [
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
]

TO_REDACT_DATA = [
    QSD_MAC,
    QSD_SERIAL,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: QnapQswConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT_CONFIG),
        "coord_data": async_redact_data(
            config_entry.runtime_data.data_coordinator.data, TO_REDACT_DATA
        ),
        "coord_fw": async_redact_data(
            config_entry.runtime_data.firmware_coordinator.data, TO_REDACT_DATA
        ),
    }
