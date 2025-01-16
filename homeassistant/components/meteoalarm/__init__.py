"""The MeteoAlarm integration."""

from __future__ import annotations

from meteoalertapi import Meteoalert

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_COUNTRY, CONF_LANGUAGE, CONF_PROVINCE, DOMAIN, LOGGER

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MeteoAlarm from a config entry."""

    country = entry.data[CONF_COUNTRY]
    province = entry.data[CONF_PROVINCE]
    language = entry.data[CONF_LANGUAGE]
    try:
        Meteoalert(country, province, language)
    except Exception:  # noqa: BLE001
        LOGGER.error(
            "Cannot connect to MeteoAlarm with country %s, province %s for language %s",
            country,
            province,
            language,
        )
        return False

    hass.data.setdefault(DOMAIN, {})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload MeteoAlarm config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle MeteoAlarm options update."""

    await hass.config_entries.async_reload(entry.entry_id)
