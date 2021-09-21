"""The Oocsi for HomeAssistant integration."""
from __future__ import annotations

from oocsi import OOCSI
import oocsi

# , OOCSIDisconnect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DATA_OOCSI

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = "switch"

# Homeassistant starting point
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oocsi for HomeAssistant from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    api = OOCSI(name, host, port)
    try:
        api.send("bob", "yes")


    except OOCSIDisconnect:
        return False

    hass.data[DATA_OOCSI] = api

    async def async_interviewer(hass: HomeAssistant):
        def handleInterviewEvent(sender, recipient, event):
            print(event)
            for K in event:
                if K in PLATFORMS:
                    platform.create(K, event[K], UID)
        api.subscribe("interviewChannel", handleInterviewEvent)
    return True

# async def setup_platform_entry(
#     hass: HomeAssistant,
#     entry: ConfigEntry,
#     platform:
# )
# async def async_interviewer(hass: HomeAssistant):


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = hass.data.pop(DATA_OOCSI)
    await api.disconnect()

    return unload_ok
