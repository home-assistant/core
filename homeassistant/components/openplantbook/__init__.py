"""The OpenPlantBook integration."""
import logging

from pyopenplantbook import OpenPlantBookApi
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, ATTR_SPECIES, ATTR_ALIAS

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the OpenPlantBook component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up OpenPlantBook from a config entry."""

    if DOMAIN not in hass.data:
        _LOGGER.debug("Creating domain in init")
        hass.data[DOMAIN] = {}
    if "API" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["API"] = OpenPlantBookApi(
            entry.data.get("client_id"), entry.data.get("secret")
        )

    def get_plant(call):
        species = call.data.get(ATTR_SPECIES)
        if species:
            plant_data = hass.data[DOMAIN]["API"].get_plantbook_data(species)
            hass.states.set(f"{DOMAIN}.plant_data", plant_data['display_pid'], plant_data.items())

    def search_plantbook(call):
        alias = call.data.get(ATTR_ALIAS)
        if alias:
            plant_data = hass.data[DOMAIN]["API"].search_plantbook(alias)
            state = len(plant_data['results'])
            attrs = {}
            for plant in plant_data['results']:
                pid = plant['pid']
                attrs[pid] = plant['display_pid']
            hass.states.set(f"{DOMAIN}.search_result", state, attrs)

    hass.services.register(DOMAIN, "search", search_plantbook)
    hass.services.register(DOMAIN, "get", get_plant)
    hass.states.set(f"{DOMAIN}.search_result", 0)
    hass.states.set(f"{DOMAIN}.plant_data", "")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data.pop(DOMAIN)

    return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
