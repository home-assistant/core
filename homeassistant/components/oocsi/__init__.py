"""The Oocsi for HomeAssistant integration."""
from __future__ import annotations
import asyncio
import json
from homeassistant.helpers import entity

from oocsi import OOCSI as oocsiApi

from voluptuous.validators import Switch

# , OOCSIDisconnect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import Config, HomeAssistant, callback

from .const import DOMAIN, DATA_OOCSI, DEVICES, DATA_INTERVIEW, OOCSI_ENTITY

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = []


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
    hass.data[DOMAIN][entry.entry_id] = oocsiApi(name, host, port)
    api = hass.data[DOMAIN][entry.entry_id]

    if OOCSI_ENTITY not in hass.data:
        hass.data[OOCSI_ENTITY] = {}
    # asyncio.create_task(_async_interviewer(hass))
    # _async_interviewer(hass, entry, api)

    # Store global variables

    hass.async_create_task(_async_interviewer(hass, entry, api))

    return True


@callback
async def _async_interviewer(hass: HomeAssistant, entry: ConfigEntry, api: api) -> bool:
    """Listen for interview replies"""

    # Retrieve global variable
    def handleInterviewEvent(sender, recipient, event):

        # addPlatform = None
        # print("incomingevent")
        # info = infoSent(sender=sender, event=event)

        if (
            bool(hass.data[OOCSI_ENTITY]) == False
            or not event.items() <= hass.data[OOCSI_ENTITY].items()
        ):
            # messageContent = json.load(event)
            hass.data[OOCSI_ENTITY] = hass.data[OOCSI_ENTITY] | event
            keys = []

            for key in hass.data[OOCSI_ENTITY]["uniquePrototype"]["components"]:
                if key not in keys:
                    keys.append(key)

                    print(keys)
            hass.config_entries.async_setup_platforms(entry, keys)
            # if key not in PLATFORMS:
            #     PLATFORMS.append(key)

    # return api.subscribe("interviewChannel", handleInterviewEvent)
    api.subscribe("interviewChannel", handleInterviewEvent)


async def platform_starter(hass: HomeAssistant, entry: ConfigEntry, api: api):
    for key in hass.data[OOCSI_ENTITY]:
        print("yes")
        print(hass.data[OOCSI_ENTITY][key], key)


async def async_create_new_platform_entity(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: api,
    entityType: entityType,
    AsyncAdd: async_add_entities,
    platform: platform,
):
    devices = []
    entities = []
    for key in hass.data[OOCSI_ENTITY]["uniquePrototype"]["components"][platform]:

        devices.append(key)
        entities.append(
            entityType(
                hass,
                key,
                api,
                hass.data[OOCSI_ENTITY]["uniquePrototype"]["components"][platform][key],
            )
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = hass.data.pop(DATA_OOCSI)
    await api.stop()

    return unload_ok

    # async def async_added_to_hass(self) -> None:
    #     def channelUpdateEvent(event):
    #         print("message")
    #         print(event["state"])

    #         self._channelState = event["state"]

    #     self._oocsi.subscribe(self._oocsichannel, channelUpdateEvent)
