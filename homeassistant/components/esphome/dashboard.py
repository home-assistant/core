"""Files to interact with a the ESPHome dashboard."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant, callback

KEY_DASHBOARD = "esphome_dashboard"


@callback
def async_get_dashboard(hass: HomeAssistant) -> ESPHomeDashboard | None:
    """Get an instance of the dashboard if set."""
    return hass.data.get(KEY_DASHBOARD)


def async_set_dashboard_info(
    hass: HomeAssistant, addon_slug: str, _host: str, _port: int
) -> None:
    """Set the dashboard info."""
    hass.data[KEY_DASHBOARD] = ESPHomeDashboard(addon_slug)


@dataclass
class ESPHomeDashboard:
    """Class to interact with the ESPHome dashboard."""

    addon_slug: str
