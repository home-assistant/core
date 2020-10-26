"""The OpenPlantBook integration."""
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

    async def get_plant(call):
        if "SPECIES" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["SPECIES"] = {}
        species = call.data.get(ATTR_SPECIES)
        if species and species not in hass.data[DOMAIN]["SPECIES"]:
            plant_data = await hass.data[DOMAIN]["API"].get_plantbook_data(species)
            if plant_data:
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
