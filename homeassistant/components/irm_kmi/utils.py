"""Helper functions for use with IRM KMI integration."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LANGUAGE_OVERRIDE, LANGS

_LOGGER = logging.getLogger(__name__)


def get_config_value(config_entry: ConfigEntry, key: str, default: Any = None) -> Any:
    """Get the value of key in the configuration.  If options were modified, they take priority."""

    if config_entry.options and key in config_entry.options:
        return config_entry.options[key]
    if config_entry.data and key in config_entry.data:
        return config_entry.data[key]
    return default


def preferred_language(hass: HomeAssistant, config_entry: ConfigEntry | None) -> str:
    """Get the preferred language for the integration if it was overridden by the configuration."""

    if (
        config_entry is None
        or get_config_value(config_entry, CONF_LANGUAGE_OVERRIDE) == "none"
    ):
        return hass.config.language if hass.config.language in LANGS else "en"

    return get_config_value(config_entry, CONF_LANGUAGE_OVERRIDE, "en")
