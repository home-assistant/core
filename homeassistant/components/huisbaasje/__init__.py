"""The Huisbaasje integration."""
import asyncio

from huisbaasje import Huisbaasje
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Huisbaasje component."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up Huisbaasje from a config entry."""
    huisbaasje = Huisbaasje(
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
    )
    user_id = config_entry.data[CONF_ID]

    hass.data.setdefault(DOMAIN, {})[user_id] = huisbaasje

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        config_entry, "sensor"
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.data[CONF_ID])

    return unload_ok
