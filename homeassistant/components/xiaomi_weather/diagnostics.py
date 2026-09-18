"""Privacy-preserving integration diagnostics."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import XiaomiWeatherConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: XiaomiWeatherConfigEntry
) -> dict[str, Any]:
    """Use an allowlist: no coordinates, names, city IDs or raw responses."""
    coordinator = entry.runtime_data
    return {
        "last_update_success": coordinator.last_update_success,
        "daily_forecast_count": len(coordinator.data.daily),
        "hourly_forecast_count": len(coordinator.data.hourly),
    }
