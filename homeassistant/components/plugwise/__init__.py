"""Plugwise platform for Home Assistant Core."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_USB_PATH, DOMAIN
from .gateway import async_setup_entry_gw, async_unload_entry_gw
from .usb import async_setup_entry_usb, async_unload_entry_usb


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Plugwise platform."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plugwise components from a config entry."""
    if entry.data.get(CONF_HOST):
        return await async_setup_entry_gw(hass, entry)
    if entry.data.get(CONF_USB_PATH):
        return await async_setup_entry_usb(hass, entry)
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the Plugwise components."""
    if entry.data.get(CONF_HOST):
        return await async_unload_entry_gw(hass, entry)
    if entry.data.get(CONF_USB_PATH):
        return await async_unload_entry_usb(hass, entry)
    return False
