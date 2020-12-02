"""The Huisbaasje integration."""
import logging

from huisbaasje import Huisbaasje, HuisbaasjeException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SOURCE_TYPES

_LOGGER = logging.getLogger(__name__)


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

    try:
        await huisbaasje.authenticate()
    except HuisbaasjeException as exception:
        _LOGGER.error("Unable to authenticate with Huisbaasje")
        raise exception

    # Load the client in the data of home assistant
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = huisbaasje

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

    # If successful, unload the Huisbaasje client
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
