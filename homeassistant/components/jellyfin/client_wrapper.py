"""Utility methods for initializing a Jellyfin client."""
from __future__ import annotations

import socket
from typing import Any

from jellyfin_apiclient_python import Jellyfin, JellyfinClient
from jellyfin_apiclient_python.api import API
from jellyfin_apiclient_python.connection_manager import (
    CONNECTION_STATE,
    ConnectionManager,
)

from homeassistant import exceptions
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CLIENT_VERSION, ITEM_KEY_IMAGE_TAGS, USER_AGENT, USER_APP_NAME


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any], client: JellyfinClient
) -> tuple[str, dict[str, Any]]:
    """Validate that the provided url and credentials can be used to connect."""
    url = user_input[CONF_URL]
    username = user_input[CONF_USERNAME]
    password = user_input[CONF_PASSWORD]

    user_id, connect_result = await hass.async_add_executor_job(
        _connect, client, url, username, password
    )

    return (user_id, connect_result)


def create_client(device_id: str, device_name: str | None = None) -> JellyfinClient:
    """Create a new Jellyfin client."""
    if device_name is None:
        device_name = socket.gethostname()

    jellyfin = Jellyfin()

    client = jellyfin.get_client()
    client.config.app(USER_APP_NAME, CLIENT_VERSION, device_name, device_id)
    client.config.http(USER_AGENT)

    return client


def _connect(
    client: JellyfinClient, url: str, username: str, password: str
) -> tuple[str, dict[str, Any]]:
    """Connect to the Jellyfin server and assert that the user can login."""
    client.config.data["auth.ssl"] = url.startswith("https")

    connect_result = _connect_to_address(client.auth, url)

    _login(client.auth, url, username, password)

    return (_get_user_id(client.jellyfin), connect_result)


def _connect_to_address(
    connection_manager: ConnectionManager, url: str
) -> dict[str, Any]:
    """Connect to the Jellyfin server."""
    result: dict[str, Any] = connection_manager.connect_to_address(url)

    if result["State"] != CONNECTION_STATE["ServerSignIn"]:
        raise CannotConnect

    return result


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


def _get_user_id(api: API) -> str:
    """Set the unique userid from a Jellyfin server."""
    settings: dict[str, Any] = api.get_user_settings()
    userid: str = settings["Id"]
    return userid


def get_artwork_url(
    client: JellyfinClient, item: dict[str, Any], max_width: int = 600
) -> str | None:
    """Find a suitable thumbnail for an item."""
    artwork_id: str = item["Id"]
    artwork_type = "Primary"
    parent_backdrop_id: str | None = item.get("ParentBackdropItemId")

    if "Backdrop" in item[ITEM_KEY_IMAGE_TAGS]:
        artwork_type = "Backdrop"
    elif parent_backdrop_id:
        artwork_type = "Backdrop"
        artwork_id = parent_backdrop_id
    elif "Primary" not in item[ITEM_KEY_IMAGE_TAGS]:
        return None

    return str(client.jellyfin.artwork(artwork_id, artwork_type, max_width))


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate the server is unreachable."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate the credentials are invalid."""
