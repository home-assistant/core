"""The Discovergy integration."""
from __future__ import annotations

import logging

import pydiscovergy
import pydiscovergy.error as discovergyError
from pydiscovergy.models import AccessToken, ConsumerToken

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    APP_NAME,
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_SECRET,
    CONF_CONSUMER_KEY,
    CONF_CONSUMER_SECRET,
    DOMAIN,
)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Discovergy from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # check if we've the necessary data in config if not do a re-auth
    if (
        CONF_CONSUMER_KEY not in entry.data
        or CONF_CONSUMER_SECRET not in entry.data
        or CONF_ACCESS_TOKEN not in entry.data
        or CONF_ACCESS_TOKEN_SECRET not in entry.data
    ):
        entry.async_start_reauth(hass)
        return False

    # init Discovergy class with tokens from config
    hass.data[DOMAIN][entry.entry_id] = pydiscovergy.Discovergy(
        app_name=APP_NAME,
        consumer_token=ConsumerToken(
            entry.data[CONF_CONSUMER_KEY], entry.data[CONF_CONSUMER_SECRET]
        ),
        access_token=AccessToken(
            entry.data[CONF_ACCESS_TOKEN], entry.data[CONF_ACCESS_TOKEN_SECRET]
        ),
    )

    try:
        # try to get data from api to check if access token is still valid
        # if no exception is raised everything is fine to go
        await hass.data[DOMAIN][entry.entry_id].get_meters()
    except discovergyError.AccessTokenExpired as err:
        _LOGGER.debug("Token expired while connecting to Discovergy: %s", err)
        entry.async_start_reauth(hass)
        return False
    except discovergyError.HTTPError as err:
        _LOGGER.error("Error connecting to Discovergy: %s", err)
        raise ConfigEntryNotReady from err

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
