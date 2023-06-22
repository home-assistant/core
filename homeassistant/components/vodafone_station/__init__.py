"""Vodafone Station integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .api import VodafoneStationApi
from .const import _LOGGER, DOMAIN

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vodafone Station platform."""
    _LOGGER.debug("Setting up Vodafone Station component")
    api = VodafoneStationApi(
        entry.data[CONF_HOST],
        entry.data[CONF_SSL],
        entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        hass=hass,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api

    await api.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        api: VodafoneStationApi = hass.data[DOMAIN][entry.entry_id]
        await api.logout()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
