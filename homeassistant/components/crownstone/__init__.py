"""Integration for Crownstone."""
import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import CrownstoneHub

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Initiate the Crownstone component."""
    conf = config.get(DOMAIN)
    hass.data[DOMAIN] = {}
    # check if config already exists for domain
    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Initiate the Crownstone API login from a config entry."""
    crownstone_hub = CrownstoneHub(hass, entry)

    if not await crownstone_hub.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = crownstone_hub

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    crownstone_hub = hass.data[DOMAIN].pop(entry.entry_id)
    return await crownstone_hub.async_reset()
