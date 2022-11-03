"""The Epic Games Store integration."""
from __future__ import annotations

from epicstore_api import EpicGamesStoreAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_LOCALE, DOMAIN
from .coordinator import EGSUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


def get_country_from_locale(locale: str) -> str:
    """Get the country code from locale."""
    excepts = {"ja": "JP", "ko": "KR", "zh-Hant": "CN"}
    return (
        excepts[locale]
        if excepts.get(locale)
        else (locale[3:] if ("-" in locale) else locale)
    ).upper()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Epic Games Store from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    api = EpicGamesStoreAPI(
        entry.data[CONF_LOCALE], get_country_from_locale(entry.data[CONF_LOCALE])
    )

    coordinator = EGSUpdateCoordinator(hass, api, entry.data[CONF_LOCALE])
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
