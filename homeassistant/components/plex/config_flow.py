"""Config flow for Plex."""
import logging

import plexapi.exceptions
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL, CONF_TOKEN, CONF_VERIFY_SSL

from .const import (  # pylint: disable=unused-import
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLEX_SERVER_CONFIG,
)
from .errors import NoServersFound, ServerNotSpecified
from .server import PlexServer

_LOGGER = logging.getLogger(__package__)


class PlexFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Plex config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Plex flow."""
        self.current_login = {}
        self.discovery_info = {}
        self.available_servers = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TOKEN, default=self.current_login.get(CONF_TOKEN, "")
                ): str
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=data_schema, errors=errors
            )

        self.current_login = user_input

        plex_server = PlexServer(user_input)
        try:
            await self.hass.async_add_executor_job(plex_server.connect)
        except NoServersFound:
            errors["base"] = "no_servers"
        except ServerNotSpecified as available_servers:
            self.available_servers = available_servers.args[0]
            return await self.async_step_select_server()
        except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized):
            _LOGGER.error("Invalid credentials provided, config not created")
            errors["base"] = "faulty_credentials"
        except (plexapi.exceptions.NotFound, requests.exceptions.ConnectionError):
            _LOGGER.error("Plex server could not be reached: %s", user_input[CONF_URL])
            errors["base"] = "not_found"
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Unknown error connecting to Plex server: %s", error)
            return self.async_abort(reason="unknown")
        else:
            if errors:
                return self.async_show_form(
                    step_id="user", data_schema=data_schema, errors=errors
                )

        server_id = plex_server.machine_identifier

        for entry in self._async_current_entries():
            if entry.data[CONF_SERVER_IDENTIFIER] == server_id:
                return self.async_abort(reason="already_configured")

        url = plex_server.url_in_use
        token = user_input.get(CONF_TOKEN)

        server_config = {CONF_URL: url}
        if token:
            server_config[CONF_TOKEN] = token
        if url.startswith("https"):
            server_config[CONF_VERIFY_SSL] = user_input.get(
                CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
            )

        _LOGGER.debug("Valid config created for %s", plex_server.friendly_name)

        return self.async_create_entry(
            title=plex_server.friendly_name,
            data={
                CONF_SERVER: plex_server.friendly_name,
                CONF_SERVER_IDENTIFIER: server_id,
                PLEX_SERVER_CONFIG: server_config,
            },
        )

    async def async_step_select_server(self, user_input=None):
        """Use selected Plex server."""
        config = dict(self.current_login)

        if user_input is None:
            configured_servers = [
                x.data[CONF_SERVER_IDENTIFIER] for x in self._async_current_entries()
            ]
            available_servers = [
                name
                for (name, server_id) in self.available_servers
                if server_id not in configured_servers
            ]
            if len(available_servers) > 1:
                return self.async_show_form(
                    step_id="select_server",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_SERVER): vol.In(available_servers)}
                    ),
                    errors={},
                )
            config[CONF_SERVER] = available_servers[0]
        else:
            config[CONF_SERVER] = user_input.get(CONF_SERVER)

        return await self.async_step_user(user_input=config)

    async def async_step_discovery(self, discovery_info):
        """Set default host and port from discovery."""
        if self._async_current_entries():
            # Skip discovery if any config already exists.
            return self.async_abort(reason="already_configured")

        self.discovery_info = discovery_info
        return await self.async_step_user()

    async def async_step_import(self, import_config):
        """Import from Plex configuration."""
        url = import_config.get(CONF_URL)
        token = import_config.get(CONF_TOKEN)
        server = import_config.get(CONF_SERVER)

        if url:
            config = {
                CONF_URL: url,
                CONF_TOKEN: token,
                CONF_VERIFY_SSL: import_config[CONF_VERIFY_SSL],
            }
        elif token:
            config = {CONF_TOKEN: token, CONF_SERVER: server}
        else:
            return self.async_abort(reason="invalid_import")

        _LOGGER.debug("Imported Plex configuration")
        return await self.async_step_user(user_input=config)
