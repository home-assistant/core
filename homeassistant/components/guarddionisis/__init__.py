"""Guard integration."""
from threading import Thread
from homeassistant.components.guarddionisis.util.util import Util
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup(hass: HomeAssistant, config: dict):
    theUtil = Util()
    thread = Thread(target = theUtil.serve, args= (hass,))
    thread.start()

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:


    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    return True