"""The Oocsi for HomeAssistant integration."""
from __future__ import annotations

import logging

from oocsi import OOCSI as oocsiApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback

from .const import DATA_OOCSI, DOMAIN, OOCSI_ENTITY

PLATFORMS = []
_LOGGER = logging.getLogger(__name__)


# Homeassistant starting point
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oocsi for HomeAssistant from a config entry."""

    # Import oocsi variables
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    # Create and save oocsi
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = oocsiApi(
        name, host, port, None, _LOGGER.info, 1
    )
    # Save oocsi connection to entity
    api = hass.data[DOMAIN][entry.entry_id]

    # Announce presence homeassistant, should be rententious soon
    api.send("heyOOCSI", {"homeassistant": "on"})
    # Create interview storage
    if OOCSI_ENTITY not in hass.data:
        hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY] = {}

    # Start interviewing process
    hass.async_create_task(_async_interviewer(hass, entry, api))

    # Finish
    return True


# Creates entities out of interviews
@callback
async def _async_interviewer(hass: HomeAssistant, entry: ConfigEntry, api):
    """Listen for interview replies."""

    def handle_interview_event(sender, recipient, event):
        # Handle interview by comparing interview entries to previous registrations
        if (
            bool(hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY]) is False
            or not event.items()
            <= hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY].items()
        ):
            # add new entries
            hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY] = (
                hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY] | event
            )
            # Check which platforms must be started for the interviewed entities

            for device in hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY]:

                for key in hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY][device][
                    "components"
                ]:

                    if (
                        hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY][device][
                            "components"
                        ][key]["type"]
                        not in PLATFORMS
                    ):
                        PLATFORMS.append(
                            hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY][device][
                                "components"
                            ][key]["type"]
                        )
                # Start platforms
            hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # Wait for interview and callback
    api.subscribe("interviewChannel", handle_interview_event)


# Create entities per platform
async def async_create_new_platform_entity(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api,
    entity_type,
    async_add_entities,
    platform,
):
    """Add entities per platform."""
    # Per platform get their entries and create an entity dictionary
    entities = []
    for device in hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY]:
        print(device)
        print(hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY])

        for key in hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY][device][
            "components"
        ]:

            if (
                hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY][device]["components"][
                    key
                ]["type"]
                == platform
            ):

                entities.append(
                    entity_type(
                        hass,
                        key,
                        api,
                        hass.data[DOMAIN][entry.entry_id][OOCSI_ENTITY][device][
                            "components"
                        ][key],
                        device,
                    )
                )
            _LOGGER.info("added %s from %s as entity", key, device)
        # Add entities
    async_add_entities(entities)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = hass.data.pop(DATA_OOCSI)
        await api.send("interviewChannel", {"homeassistant": "off"})
        await api.stop()

    return unload_ok
