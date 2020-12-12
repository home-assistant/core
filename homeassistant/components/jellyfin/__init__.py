"""The jellyfin integration."""
import asyncio
import uuid
import socket
import logging

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from jellyfin_apiclient_python import Jellyfin, JellyfinClient
from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

from .const import (  # pylint:disable=unused-import
    DOMAIN,
    USER_APP_NAME,
    USER_AGENT,
    CLIENT_VERSION,
    DATA_CLIENT,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the jellyfin component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up jellyfin from a config entry."""

    class CannotConnect(exceptions.HomeAssistantError):
        """Error to indicate we cannot connect."""

    class InvalidAuth(exceptions.HomeAssistantError):
        """Error to indicate there is invalid auth."""

    def setup_client(jellyfin: Jellyfin):
        client = jellyfin.get_client()

        player_name = socket.gethostname()
        client_uuid = str(uuid.uuid4())

        client.config.app(USER_APP_NAME, CLIENT_VERSION, player_name, client_uuid)
        client.config.http(USER_AGENT)

    def authenticate(client: JellyfinClient, url, username, password) -> bool:
        client.config.data["auth.ssl"] = True if url.startswith("https") else False

        state = client.auth.connect_to_address(url)
        if state["State"] != CONNECTION_STATE["ServerSignIn"]:
            _LOGGER.exception(
                "Unable to connect to: %s. Connection State: %s", url, state["State"]
            )
            raise CannotConnect

        response = client.auth.login(url, username, password)
        if "AccessToken" not in response:
            raise InvalidAuth

        return True

    jellyfin = Jellyfin()
    setup_client(jellyfin)

    url = entry.data.get("url")
    username = entry.data.get("username")
    password = entry.data.get("password")

    connected = await hass.async_add_executor_job(
        authenticate, jellyfin.get_client(), url, username, password
    )

    if connected:
        _LOGGER.debug("Adding API to domain data storage for entry %s", entry.entry_id)

        client = jellyfin.get_client()

        hass.data[DOMAIN][entry.entry_id] = {DATA_CLIENT: client}

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    return True
