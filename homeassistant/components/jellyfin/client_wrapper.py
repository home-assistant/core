"""Utility methods for initializing a Jellyfin client."""
from __future__ import annotations

import socket
from typing import Any
import uuid

from jellyfin_apiclient_python import Jellyfin, JellyfinClient
from jellyfin_apiclient_python.api import API
from jellyfin_apiclient_python.connection_manager import (
    CONNECTION_STATE,
    ConnectionManager,
)

from homeassistant import exceptions
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CLIENT_VERSION, USER_AGENT, USER_APP_NAME


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any], client: JellyfinClient
) -> str:
    """Validate that the provided url and credentials can be used to connect."""
    url = user_input[CONF_URL]
    username = user_input[CONF_USERNAME]
    password = user_input[CONF_PASSWORD]

    userid = await hass.async_add_executor_job(
        _connect, client, url, username, password
    )

    return userid


def create_client() -> JellyfinClient:
    """Create a new Jellyfin client."""
    jellyfin = Jellyfin()
    client = jellyfin.get_client()
    _setup_client(client)
    return client


def _setup_client(client: JellyfinClient) -> None:
    """Configure the Jellyfin client with a number of required properties."""
    player_name = socket.gethostname()
    client_uuid = str(uuid.uuid4())

    client.config.app(USER_APP_NAME, CLIENT_VERSION, player_name, client_uuid)
    client.config.http(USER_AGENT)


def _connect(client: JellyfinClient, url: str, username: str, password: str) -> str:
    """Connect to the Jellyfin server and assert that the user can login."""
    client.config.data["auth.ssl"] = url.startswith("https")

    _connect_to_address(client.auth, url)
    _login(client.auth, url, username, password)
    return _get_id(client.jellyfin)


def _connect_to_address(connection_manager: ConnectionManager, url: str) -> None:
    """Connect to the Jellyfin server."""
    state = connection_manager.connect_to_address(url)
    if state["State"] != CONNECTION_STATE["ServerSignIn"]:
        raise CannotConnect


def _login(
    connection_manager: ConnectionManager,
    url: str,
    username: str,
    password: str,
) -> None:
    """Assert that the user can log in to the Jellyfin server."""
    response = connection_manager.login(url, username, password)
    if "AccessToken" not in response:
        raise InvalidAuth


def _get_id(api: API) -> str:
    """Set the unique userid from a Jellyfin server."""
    settings: dict[str, Any] = api.get_user_settings()
    userid: str = settings["Id"]
    return userid


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate the server is unreachable."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate the credentials are invalid."""
