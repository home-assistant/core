"""Energy platform."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import VRMForecastsDataUpdateCoordinator


async def async_get_solar_forecast(
    hass: HomeAssistant, config_entry_id: str
) -> dict[str, dict[str, float | int]] | None:
    """Get solar forecast for a config entry ID."""
    if (
        entry := hass.config_entries.async_get_entry(config_entry_id)
    ) is None or not isinstance(entry.runtime_data, VRMForecastsDataUpdateCoordinator):
        return None

    return {"wh_hours": entry.runtime_data.data.solar.get_dict_isoformat}
