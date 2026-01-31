"""Victron Remote Monitoring energy platform."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def async_get_solar_forecast(
    hass: HomeAssistant, config_entry_id: str
) -> dict[str, dict[str, float | int]] | None:
    """Get solar forecast for a config entry ID."""
    if (
        entry := hass.config_entries.async_get_entry(config_entry_id)
    ) is None or entry.state != ConfigEntryState.LOADED:
        return None
    data = entry.runtime_data.data.solar
    if data is None:
        return None

    return {"wh_hours": data.get_dict_isoformat}
