"""The openevse component."""

import logging

from openevsewifi import Charger, InvalidAuthentication

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import DATA_CHARGER, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Charger from a config entry."""
    host_with_port = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
    charger = Charger(
        host=host_with_port,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        status = await hass.async_add_executor_job(Charger.status.fget, charger)
        _LOGGER.info("Connected to charger with status '%s'", status)
    except InvalidAuthentication:
        _LOGGER.error(
            "Login to %s failed: Invalid authentication",
            host_with_port,
        )
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CHARGER: charger,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok
