"""The OpenPlantBook integration."""
import asyncio
import logging

from pyopenplantbook import OpenPlantBookApi
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id

from .const import ATTR_ALIAS, ATTR_SPECIES, DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the OpenPlantBook component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up OpenPlantBook from a config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if "API" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["API"] = OpenPlantBookApi(
            entry.data.get("client_id"), entry.data.get("secret")
        )
    if "SPECIES" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["SPECIES"] = {}

    async def get_plant(call):
        species = call.data.get(ATTR_SPECIES)
        if species:
            # Here we try to ensure that we only run one API request for each species
            # The first process creates an empty dict, and access the API
            # Later requests for the same species either wait for the first one to complete
            # or they returns immediately if we already have the data we need
            _LOGGER.debug("get_plant %s", species)
            if species not in hass.data[DOMAIN]["SPECIES"]:
                _LOGGER.debug("I am the first process %s", species)
                hass.data[DOMAIN]["SPECIES"][species] = {}
            elif "pid" not in hass.data[DOMAIN]["SPECIES"][species]:
                # If more than one "get_plant" is triggered for the same species, we wait for up to
                # 10 seconds for the first process to complete the API request.
                # We don't want to return immediately, as we want the state object to be set by
                # the running process before we return from this call
                _LOGGER.debug(
                    "Another process is currently trying to get the data for %s...",
                    species,
                )
                wait = 0
                while "pid" not in hass.data[DOMAIN]["SPECIES"][species]:
                    _LOGGER.debug("Waiting...")
                    wait = wait + 1
                    if wait == 10:
                        _LOGGER.error("Giving up waiting for OpenPlantBook")
                        return False
                    await asyncio.sleep(1)
                _LOGGER.debug("The other process completed successfully")
                return True
            else:
                # We already have the data we need, so let's just return
                _LOGGER.debug("We already have data for %s", species)
                return True

            plant_data = await hass.data[DOMAIN]["API"].get_plantbook_data(species)
            if plant_data:
                _LOGGER.debug("Got data for %s", species)
                hass.data[DOMAIN]["SPECIES"][species] = plant_data
                attrs = {}
                for var, val in plant_data.items():
                    attrs[var] = val
                entity_id = async_generate_entity_id(
                    f"{DOMAIN}" + ".{}", plant_data["pid"], hass=hass
                )
                hass.states.async_set(entity_id, plant_data["display_pid"], attrs)

    async def search_plantbook(call):
        alias = call.data.get(ATTR_ALIAS)
        if alias:
            plant_data = await hass.data[DOMAIN]["API"].search_plantbook(alias)
            state = len(plant_data["results"])
            attrs = {}
            for plant in plant_data["results"]:
                pid = plant["pid"]
                attrs[pid] = plant["display_pid"]
            hass.states.async_set(f"{DOMAIN}.search_result", state, attrs)

    hass.services.async_register(DOMAIN, "search", search_plantbook)
    hass.services.async_register(DOMAIN, "get", get_plant)
    hass.states.async_set(f"{DOMAIN}.search_result", 0)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data.pop(DOMAIN)

    return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
