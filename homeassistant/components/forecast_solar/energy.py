"""Energy platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .coordinator import ForecastSolarDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_get_solar_forecast(
    hass: HomeAssistant, config_entry_id: str
) -> dict[str, dict[str, float | int]] | None:
    """Get solar forecast for a config entry ID."""
    if (
        entry := hass.config_entries.async_get_entry(config_entry_id)
    ) is None or not isinstance(entry.runtime_data, ForecastSolarDataUpdateCoordinator):
        return None

    return {
        "wh_hours": {
            timestamp.isoformat(): val
            for timestamp, val in entry.runtime_data.data.wh_period.items()
        }
    }
