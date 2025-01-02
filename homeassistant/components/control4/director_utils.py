"""Provides data updates from the Control4 controller for platforms."""

from collections import defaultdict
import logging
from typing import Any

from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import BadToken

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_ACCOUNT, CONF_CONTROLLER_UNIQUE_ID, CONF_DIRECTOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _update_variables_for_config_entry(
    hass: HomeAssistant, entry: ConfigEntry, variable_names: set[str]
) -> dict[int, dict[str, Any]]:
    """Retrieve data from the Control4 director."""
    director: C4Director = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR]
    data = await director.getAllItemVariableValue(variable_names)
    result_dict: defaultdict[int, dict[str, Any]] = defaultdict(dict)
    for item in data:
        result_dict[item["id"]][item["varName"]] = item["value"]
    return dict(result_dict)


async def update_variables_for_config_entry(
    hass: HomeAssistant, entry: ConfigEntry, variable_names: set[str]
) -> dict[int, dict[str, Any]]:
    """Try to Retrieve data from the Control4 director for update_coordinator."""
    try:
        return await _update_variables_for_config_entry(hass, entry, variable_names)
    except BadToken:
        _LOGGER.debug("Updating Control4 director token")
        await refresh_tokens(hass, entry)
        return await _update_variables_for_config_entry(hass, entry, variable_names)


async def refresh_tokens(hass: HomeAssistant, entry: ConfigEntry):
    """Store updated authentication and director tokens in hass.data."""
    config = entry.data
    account_session = aiohttp_client.async_get_clientsession(hass)

    account = C4Account(config[CONF_USERNAME], config[CONF_PASSWORD], account_session)
    await account.getAccountBearerToken()

    controller_unique_id = config[CONF_CONTROLLER_UNIQUE_ID]
    director_token_dict = await account.getDirectorBearerToken(controller_unique_id)
    director_session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)

    director = C4Director(
        config[CONF_HOST], director_token_dict[CONF_TOKEN], director_session
    )

    _LOGGER.debug("Saving new tokens in hass data")
    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data[CONF_ACCOUNT] = account
    entry_data[CONF_DIRECTOR] = director
