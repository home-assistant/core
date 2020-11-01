"""The Huisbaasje integration."""
import logging

from huisbaasje import Huisbaasje
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN, SOURCE_TYPES

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Huisbaasje component."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up Huisbaasje from a config entry."""
    # Create the Huisbaasje client
    huisbaasje = Huisbaasje(
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        source_types=SOURCE_TYPES,
    )
    user_id = config_entry.data[CONF_ID]

    # Load the client in the data of home assistant
    hass.data.setdefault(DOMAIN, {})[user_id] = huisbaasje

    # Offload the loading of entities to the platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    # Forward the unloading of the entry to the platform
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        config_entry, "sensor"
    )

    # If successfull, unload the Huisbaasje client
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.data[CONF_ID])

    return unload_ok
