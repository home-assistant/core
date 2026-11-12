"""Helper functions for use with IRM KMI integration."""

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

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
