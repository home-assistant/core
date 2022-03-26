"""Energy platform."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_solar_forecast(
    hass: HomeAssistant, config_entry_id: str
) -> dict[str, dict[str, float | int]] | None:
    """Get solar forecast for a config entry ID."""
    if (coordinator := hass.data[DOMAIN].get(config_entry_id)) is None:
        return None

    return {
        "wh_hours": {
            timestamp.isoformat(): val
            for timestamp, val in coordinator.data.wh_hours.items()
        }
    }
