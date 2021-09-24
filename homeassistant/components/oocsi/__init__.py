"""The Oocsi for HomeAssistant integration."""
from __future__ import annotations
import asyncio

from oocsi import OOCSI as oocsiApi

from voluptuous.validators import Switch

# , OOCSIDisconnect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import Config, HomeAssistant, callback

from .const import DOMAIN, DATA_OOCSI, DEVICES, DATA_INTERVIEW

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["switch"]
OOCSI_ENTITY = "OOCSI_ENTITY"

# Creates entities out of interviews


# Homeassistant starting point
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oocsi for HomeAssistant from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    hass.data.setdefault(DOMAIN, {})
    api = oocsiApi(name, host, port)
    hass.data[DATA_OOCSI] = api

    if OOCSI_ENTITY not in hass.data:
        hass.data[OOCSI_ENTITY] = {}
    # asyncio.create_task(_async_interviewer(hass))
    # _async_interviewer(hass, entry, api)

    # Store global variables

    devices = ("Switch", "name")
    hass.async_create_task(_async_interviewer(hass, entry, api))
    hass.data[DOMAIN][entry.entry_id] = devices

    return True


@callback
async def _async_interviewer(hass: HomeAssistant, entry: ConfigEntry, api: api) -> bool:
    """Listen for interview replies"""

    # Retrieve global variable
    def handleInterviewEvent(sender, recipient, event):

        # addPlatform = None
        # print(event)
        # info = infoSent(sender=sender, event=event)
        if event != hass.data[OOCSI_ENTITY]:

            hass.data[OOCSI_ENTITY] = hass.data[OOCSI_ENTITY] | event
            print(hass.data[OOCSI_ENTITY])

    # return api.subscribe("interviewChannel", handleInterviewEvent)
    api.subscribe("interviewChannel", handleInterviewEvent)


async def platform_starter(hass: HomeAssistant, entry: ConfigEntry, api: api):
    for key in hass.data[OOCSI_ENTITY]:
        print("yes")
        print(hass.data[OOCSI_ENTITY][key], key)
        hass.config_entries.async_setup_platforms(hass.data[OOCSI_ENTITY][key], key)


async def async_create_new_platform_entity(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: api,
    typeI: entityType,
):

    print("here")
    for k in eventData:
        if eventData(k) == type(typeI).__name__:
            entity = [typeI(device, api)]
            async_add_entities(entity, True)


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
    await api.stop()

    return unload_ok
