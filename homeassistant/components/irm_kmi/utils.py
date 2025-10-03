"""Helper functions for use with IRM KMI integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LANGUAGE_OVERRIDE, LANGS


def preferred_language(hass: HomeAssistant, config_entry: ConfigEntry | None) -> str:
    """Get the preferred language for the integration if it was overridden by the configuration."""

    if (
        config_entry is None
        or config_entry.options.get(CONF_LANGUAGE_OVERRIDE) == "none"
    ):
        return hass.config.language if hass.config.language in LANGS else "en"

    return config_entry.options.get(CONF_LANGUAGE_OVERRIDE, "en")
