"""Provides data updates from the Control4 controller for platforms."""
import logging

from pyControl4.error_handling import BadToken

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DIRECTOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def director_update_data(
    hass: HomeAssistant, entry: ConfigEntry, var: str
) -> dict:
    """Retrieve data from the Control4 director for update_coordinator."""
    # possibly implement usage of director_token_expiration to start
    # token refresh without waiting for error to occur
    try:
        director = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR]
        data = await director.getAllItemVariableValue(var)
    except BadToken:
        _LOGGER.info("Updating Control4 director token")
        await refresh_tokens(hass, entry)
        director = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR]
        data = await director.getAllItemVariableValue(var)
    return {key["id"]: key for key in data}


async def refresh_tokens(hass: HomeAssistant, entry: ConfigEntry):
    """Rerun setup to update tokens for all entities."""
    await hass.config_entries.async_reload(entry.entry_id)
