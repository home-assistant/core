"""The Oocsi for HomeAssistant integration."""
from __future__ import annotations
import asyncio
import json
from homeassistant.helpers import entity

from oocsi import OOCSI as oocsiApi

from voluptuous.validators import Switch

# , OOCSIDisconnect

from homeassistant.config_entries import ConfigEntry, EntityRegistryDisabledHandler
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

    # Import oocsi variables
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    # Create and save oocsi
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = oocsiApi(name, host, port)
    api = hass.data[DOMAIN][entry.entry_id]

    # Create interview storage
    if OOCSI_ENTITY not in hass.data:
        hass.data[OOCSI_ENTITY] = {}

    # Start interviewing process
    hass.async_create_task(_async_interviewer(hass, entry, api))

    # Finish
    return True


@callback
async def _async_interviewer(hass: HomeAssistant, entry: ConfigEntry, api: api) -> bool:
    """Listen for interview replies"""

    def handleInterviewEvent(sender, recipient, event):

        # Handle interview by comparing interview entries to previous registrations
        if (
            bool(hass.data[OOCSI_ENTITY]) == False
            or not event.items() <= hass.data[OOCSI_ENTITY].items()
        ):
            # add new entries
            hass.data[OOCSI_ENTITY] = hass.data[OOCSI_ENTITY] | event

            # Check which platforms must be started for the interviewed entities
            for key in hass.data[OOCSI_ENTITY]["uniquePrototype"]["components"]:
                if key not in PLATFORMS:
                    PLATFORMS.append(key)
            # Start platforms
            hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # Wait for interview and callback
    api.subscribe("interviewChannel", handleInterviewEvent)


# Create entities per platform
async def async_create_new_platform_entity(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: api,
    entityType: entityType,
    AsyncAdd: async_add_entities,
    platform: platform,
):
    # Per platform get their entries and create an entity dictionary
    entities = []
    for key in hass.data[OOCSI_ENTITY]["uniquePrototype"]["components"][platform]:

        entities.append(
            entityType(
                hass,
                key,
                api,
                hass.data[OOCSI_ENTITY]["uniquePrototype"]["components"][platform][key],
            )
        )
    # Add entities
    AsyncAdd(entities)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = hass.data.pop(DATA_OOCSI)
    await api.stop()

    return unload_ok
