"""The Meraki integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery

from .const import CONF_SECRET, CONF_VALIDATOR, DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Meraki integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Meraki from a config entry."""
    await discovery.async_load_platform(
        hass,
        Platform.DEVICE_TRACKER,
        DOMAIN,
        {
            CONF_VALIDATOR: entry.data[CONF_VALIDATOR],
            CONF_SECRET: entry.data[CONF_SECRET],
        },
        {},
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Meraki config entry."""
    return True
