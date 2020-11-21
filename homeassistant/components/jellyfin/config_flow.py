"""Config flow for jellyfin integration."""
import logging
import uuid
import socket

import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from jellyfin_apiclient_python import Jellyfin
from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE

from .const import (  # pylint:disable=unused-import
    DOMAIN,
    USER_APP_NAME,
    USER_AGENT,
    CLIENT_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema({"url": str, "username": str, "password": str})


class JellyfinHub:
    def __init__(self):
        """Initialize."""
        self.jellyfin = Jellyfin()
        self.setup_client()

    def setup_client(self):
        client = self.jellyfin.get_client()

        player_name = socket.gethostname()
        client_uuid = str(uuid.uuid4())

        client.config.app(USER_APP_NAME, CLIENT_VERSION, player_name, client_uuid)
        client.config.http(USER_AGENT)

    def authenticate(self, url: str, username: str, password: str) -> bool:
        client = self.jellyfin.get_client()

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


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = JellyfinHub()

    await hass.async_add_executor_job(
        hub.authenticate, data["url"], data["username"], data["password"]
    )

    return {"title": "default"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for jellyfin."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
