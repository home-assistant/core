"""Diagnostics support for switchbot integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_ENCRYPTION_KEY, CONF_KEY_ID
from .coordinator import SwitchbotConfigEntry

_logger = logging.getLogger(__name__)

TO_REDACT = [CONF_KEY_ID, CONF_ENCRYPTION_KEY]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SwitchbotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    _logger.info("Gathering diagnostics for Switchbot config entry: %s", entry.entry_id)
    _logger.info("Gathering entry.runtime_data.data: %s", entry.runtime_data.data)
    _logger.info("Config entry data: %s", coordinator.data)
    _logger.info("Config entry ble_device: %s", coordinator.ble_device)
    _logger.info("Config entry device: %s", coordinator.device)
    _logger.info("Config entry base_unique_id: %s", coordinator.base_unique_id)
    _logger.info("Config entry device_name: %s", coordinator.device_name)
    _logger.info("Config entry connectable: %s", coordinator.connectable)
    _logger.info("Config entry model: %s", coordinator.model)

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
    }
