"""Provides data updates from the Control4 controller for platforms."""
from collections import defaultdict
from collections.abc import Sequence
import logging

from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import BadToken

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_ACCOUNT, CONF_CONTROLLER_UNIQUE_ID, CONF_DIRECTOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def update_variables_for_entity(
    hass: HomeAssistant, entry: ConfigEntry, variable_names: Sequence[str]
) -> dict[int, dict[str, bool | int | str | dict]]:
    """Retrieve data from the Control4 director for update_coordinator."""
    try:
        director = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR]
        data = await director.getAllItemVariableValue(variable_names)
        result_dict: defaultdict[int, dict[str, bool | int | str | dict]] = defaultdict(
            dict
        )
        for item in data:
            typ = item.get("type", None)
            value = item["value"]
            if typ == "Boolean":
                value = bool(int(value))
            elif typ == "Number":
                value = float(value)

            result_dict[int(item["id"])][item["varName"]] = value
        return dict(result_dict)
    except BadToken:
        _LOGGER.info("Updating Control4 director token")
        await refresh_tokens(hass, entry)
        return await update_variables_for_entity(hass, entry, variable_names)


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
