"""Helper functions for use with IRM KMI integration."""

from typing import TYPE_CHECKING

from irm_kmi_api import RadarForecast

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import CONF_LANGUAGE_OVERRIDE, LANGS

if TYPE_CHECKING:
    from .coordinator import IrmKmiConfigEntry


def preferred_language(hass: HomeAssistant, config_entry: IrmKmiConfigEntry) -> str:
    """Return the language to use for this config entry.

    Falls back to the Home Assistant language, or to English when that one is
    not supported.
    """
    language: str = config_entry.options.get(CONF_LANGUAGE_OVERRIDE, "none")
    if language == "none":
        return hass.config.language if hass.config.language in LANGS else "en"
    return language


def current_radar_frame(radar_forecast: list[RadarForecast]) -> int:
    """Return the index of the last radar frame at or before now, clamped to 0."""
    now = dt_util.utcnow()
    started = sum(
        dt_util.parse_datetime(forecast["datetime"], raise_on_error=True) <= now
        for forecast in radar_forecast
    )
    return max(started - 1, 0)
