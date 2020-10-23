"""The OpenPlantBook integration."""
import logging

from openplantbook import OpenPlantBookApi
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data.pop(DOMAIN)

    return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
