"""The Flick Electric integration."""

from datetime import datetime as dt
import logging

import jwt
from pyflick import FlickAPI
from pyflick.authentication import AbstractFlickAuth
from pyflick.const import DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_TOKEN_EXPIRY, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_ID_TOKEN = "id_token"

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flick Electric from a config entry."""
    auth = HassFlickAuth(hass, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = FlickAPI(auth)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class HassFlickAuth(AbstractFlickAuth):
    """Implementation of AbstractFlickAuth based on a Home Assistant entity config."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Flick authentication based on a Home Assistant entity config."""
        super().__init__(aiohttp_client.async_get_clientsession(hass))
        self._entry = entry
        self._hass = hass

    async def _get_entry_token(self):
        # No token saved, generate one
        if (
            CONF_TOKEN_EXPIRY not in self._entry.data
            or CONF_ACCESS_TOKEN not in self._entry.data
        ):
            await self._update_token()

        # Token is expired, generate a new one
        if self._entry.data[CONF_TOKEN_EXPIRY] <= dt.now().timestamp():
            await self._update_token()

        return self._entry.data[CONF_ACCESS_TOKEN]

    async def _update_token(self):
        _LOGGER.debug("Fetching new access token")

        token = await self.get_new_token(
            username=self._entry.data[CONF_USERNAME],
            password=self._entry.data[CONF_PASSWORD],
            client_id=self._entry.data.get(CONF_CLIENT_ID, DEFAULT_CLIENT_ID),
            client_secret=self._entry.data.get(
                CONF_CLIENT_SECRET, DEFAULT_CLIENT_SECRET
            ),
        )

        _LOGGER.debug("New token: %s", token)

        # Flick will send the same token, but expiry is relative - so grab it from the token
        token_decoded = jwt.decode(
            token[CONF_ID_TOKEN], options={"verify_signature": False}
        )

        self._hass.config_entries.async_update_entry(
            self._entry,
            data={
                **self._entry.data,
                CONF_ACCESS_TOKEN: token,
                CONF_TOKEN_EXPIRY: token_decoded["exp"],
            },
        )

    async def async_get_access_token(self):
        """Get Access Token from HASS Storage."""
        token = await self._get_entry_token()

        return token[CONF_ID_TOKEN]
