"""Common code for tplink."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback

from .const import DOMAIN


@callback
def async_entry_is_legacy(entry: ConfigEntry) -> bool:
    """Check if a config entry is the legacy shared one."""
    return entry.unique_id is None or entry.unique_id == DOMAIN
