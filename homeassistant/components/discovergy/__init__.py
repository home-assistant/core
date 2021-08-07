"""The Discovergy integration."""
from __future__ import annotations

import logging

from pydiscovergy import Discovergy
import pydiscovergy.error as discovergyError
from pydiscovergy.models import ConsumerToken, RequestToken

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

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


async def async_setup(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Discovergy component."""
    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Discovergy from a config entry."""

    if not entry.data[CONF_CONSUMER_KEY] or not entry.data[CONF_CONSUMER_SECRET]:
        hass.data[DOMAIN][entry.entry_id] = Discovergy(
            APP_NAME, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
        )
    else:
        # uses stored consumer token pair from config
        hass.data[DOMAIN][entry.entry_id] = Discovergy(
            APP_NAME,
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
            consumer_token=ConsumerToken(
                entry.data[CONF_CONSUMER_KEY], entry.data[CONF_CONSUMER_SECRET]
            ),
        )

    try:
        conf_access_token = None
        if entry.data[CONF_ACCESS_TOKEN] and entry.data[CONF_ACCESS_TOKEN_SECRET]:
            _LOGGER.debug("Reusing access token from config")
            conf_access_token = RequestToken(
                entry.data[CONF_ACCESS_TOKEN], entry.data[CONF_ACCESS_TOKEN_SECRET]
            )

        access_token = await hass.data[DOMAIN][entry.entry_id].login(
            access_token=conf_access_token
        )

        # now update the config entry with the access token if we haven't got it from config
        if conf_access_token is None:
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_ACCESS_TOKEN: access_token.token,
                    CONF_ACCESS_TOKEN_SECRET: access_token.token_secret,
                },
            )
    except discovergyError.InvalidLogin as err:
        _LOGGER.error("Error authenticate to Discovergy: %s", err)
        return False
    except discovergyError.HTTPError as err:
        _LOGGER.error("Error connecting to Discovergy: %s", err)
        return False

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
