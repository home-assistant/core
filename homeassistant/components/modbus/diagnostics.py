"""Diagnostics support for modbus.

Remark: diagnostic is added to satisfy the gold/platinum quality demand,
it does NOT replace the need for debug files to solve problms.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {"data": entry.data}
