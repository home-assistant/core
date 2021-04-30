"""Config flow for the Jellyfin integration."""
from __future__ import annotations

import logging
import socket
from typing import Any
import uuid

from jellyfin_apiclient_python import Jellyfin, JellyfinClient
from jellyfin_apiclient_python.connection_manager import (
    CONNECTION_STATE,
    ConnectionManager,
)
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CLIENT_VERSION, DOMAIN, USER_AGENT, USER_APP_NAME

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jellyfin."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a user defined configuration."""
        await self.async_set_unique_id(DOMAIN)

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as ex:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(ex)
            else:
                title = str(user_input.get(CONF_URL))
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> JellyfinClient:
    """Validate that the provided url and credentials can be used to connect."""
    jellyfin = Jellyfin()
    client = jellyfin.get_client()
    _setup_client(client)

    url = user_input.get(CONF_URL)
    username = user_input.get(CONF_USERNAME)
    password = user_input.get(CONF_PASSWORD)

    await hass.async_add_executor_job(_connect, client, url, username, password)

    return client


def _setup_client(client: JellyfinClient) -> None:
    """Configure the Jellyfin client with a number of required properties."""
    player_name = socket.gethostname()
    client_uuid = str(uuid.uuid4())

    client.config.app(USER_APP_NAME, CLIENT_VERSION, player_name, client_uuid)
    client.config.http(USER_AGENT)


def _connect(client: JellyfinClient, url: str, username: str, password: str) -> bool:
    """Connect to the Jellyfin server and assert that the user can login."""
    client.config.data["auth.ssl"] = url.startswith("https")

    _connect_to_address(client.auth, url)
    _login(client.auth, url, username, password)

    return True


def _connect_to_address(connection_manager: ConnectionManager, url: str) -> None:
    """Connect to the Jellyfin server."""
    state = connection_manager.connect_to_address(url)
    if state["State"] != CONNECTION_STATE["ServerSignIn"]:
        _LOGGER.error(
            "Unable to connect to: %s. Connection State: %s",
            url,
            state["State"],
        )
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


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate the server is unreachable."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate the credentials are invalid."""
