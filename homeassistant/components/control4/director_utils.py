import logging

from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import BadToken

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCOUNT,
    CONF_CONTROLLER_NAME,
    CONF_DIRECTOR,
    CONF_DIRECTOR_TOKEN_EXPIRATION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def director_update_data(
    hass: HomeAssistant, entry: ConfigEntry, var: str
) -> dict:
    """Retrieve data from the Control4 director for update_coordinator."""
    try:
        director = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR]
        data = await director.getAllItemVariableValue(var)
    except BadToken:
        _LOGGER.info("Updating Control4 director token")
        await refresh_tokens(hass, entry)
        director = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR]
        data = await director.getAllItemVariableValue(var)
    return_dict = {}
    for key in data:
        return_dict[key["id"]] = key
    return return_dict


async def refresh_tokens(hass: HomeAssistant, entry: ConfigEntry):
    """Store updated authentication and director tokens in hass.data."""
    config = entry.data
    account = C4Account(config[CONF_USERNAME], config[CONF_PASSWORD])
    controller_name = config[CONF_CONTROLLER_NAME]
    director_token_dict = await account.getDirectorBearerToken(controller_name)
    director = C4Director(config[CONF_HOST], director_token_dict[CONF_TOKEN])
    director_token_expiry = director_token_dict["token_expiration"]

    _LOGGER.debug("Saving new tokens in config_entry")
    hass.data[DOMAIN][entry.entry_id][CONF_ACCOUNT] = account
    hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR] = director
    hass.data[DOMAIN][entry.entry_id][
        CONF_DIRECTOR_TOKEN_EXPIRATION
    ] = director_token_expiry
