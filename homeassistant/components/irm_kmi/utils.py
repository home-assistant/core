"""Helper functions for use with IRM KMI integration."""

from typing import TYPE_CHECKING

from irm_kmi_api import RadarStyle

from homeassistant.core import HomeAssistant

from .const import CONF_DARK_MODE, CONF_LANGUAGE_OVERRIDE, CONF_RADAR_STYLE, LANGS

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


def radar_options(config_entry: IrmKmiConfigEntry) -> tuple[RadarStyle, bool]:
    """Return the radar style and dark mode of a config entry."""
    return (
        RadarStyle(
            config_entry.options.get(CONF_RADAR_STYLE, RadarStyle.OPTION_STYLE_STD)
        ),
        config_entry.options.get(CONF_DARK_MODE, False),
    )
