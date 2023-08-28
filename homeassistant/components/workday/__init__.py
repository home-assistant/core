"""Sensor to indicate whether the current day is a workday."""
from __future__ import annotations

from holidays import list_supported_countries

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_COUNTRY, CONF_PROVINCE, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Workday from a config entry."""

    country: str = entry.options[CONF_COUNTRY]
    province: str | None = entry.options.get(CONF_PROVINCE)
    if country and country not in list_supported_countries():
        raise ConfigEntryError(f"Selected country {country} is not valid")

    if province and province not in list_supported_countries()[country]:
        raise ConfigEntryError(
            f"Selected province {province} for country {country} is not valid"
        )

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Workday config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
