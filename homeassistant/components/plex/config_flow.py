"""Config flow for Plex."""
import logging

import plexapi.exceptions
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL, CONF_TOKEN, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.util.json import load_json

from .const import (  # pylint: disable=unused-import
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLEX_CONFIG_FILE,
    PLEX_SERVER_CONFIG,
)
from .errors import NoServersFound, ServerNotSpecified
from .server import PlexServer

USER_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})

_LOGGER = logging.getLogger(__package__)


@callback
def configured_servers(hass):
    """Return a set of the configured Plex servers."""
    return set(
        entry.data[CONF_SERVER_IDENTIFIER]
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


class PlexFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Plex config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Plex flow."""
        self.current_login = {}
        self.available_servers = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return await self.async_step_server_validate(user_input)

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors={})

    async def async_step_server_validate(self, server_config):
        """Validate a provided configuration."""
        errors = {}
        self.current_login = server_config

        plex_server = PlexServer(server_config)
        try:
            await self.hass.async_add_executor_job(plex_server.connect)

        except NoServersFound:
            errors["base"] = "no_servers"
        except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized):
            _LOGGER.error("Invalid credentials provided, config not created")
            errors["base"] = "faulty_credentials"
        except (plexapi.exceptions.NotFound, requests.exceptions.ConnectionError):
            _LOGGER.error(
                "Plex server could not be reached: %s", server_config[CONF_URL]
            )
            errors["base"] = "not_found"

        except ServerNotSpecified as available_servers:
            self.available_servers = available_servers.args[0]
            return await self.async_step_select_server()

        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Unknown error connecting to Plex server: %s", error)
            return self.async_abort(reason="unknown")

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=USER_SCHEMA, errors=errors
            )

        server_id = plex_server.machine_identifier

        for entry in self._async_current_entries():
            if entry.data[CONF_SERVER_IDENTIFIER] == server_id:
                return self.async_abort(reason="already_configured")

        url = plex_server.url_in_use
        token = server_config.get(CONF_TOKEN)

        entry_config = {CONF_URL: url}
        if token:
            entry_config[CONF_TOKEN] = token
        if url.startswith("https"):
            entry_config[CONF_VERIFY_SSL] = server_config.get(
                CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
            )

        _LOGGER.debug("Valid config created for %s", plex_server.friendly_name)

        return self.async_create_entry(
            title=plex_server.friendly_name,
            data={
                CONF_SERVER: plex_server.friendly_name,
                CONF_SERVER_IDENTIFIER: server_id,
                PLEX_SERVER_CONFIG: entry_config,
            },
        )

    async def async_step_select_server(self, user_input=None):
        """Use selected Plex server."""
        config = dict(self.current_login)
        if user_input is not None:
            config[CONF_SERVER] = user_input[CONF_SERVER]
            return await self.async_step_server_validate(config)

        configured = configured_servers(self.hass)
        available_servers = [
            name
            for (name, server_id) in self.available_servers
            if server_id not in configured
        ]

        if not available_servers:
            return self.async_abort(reason="all_configured")
        if len(available_servers) == 1:
            config[CONF_SERVER] = available_servers[0]
            return await self.async_step_server_validate(config)

        return self.async_show_form(
            step_id="select_server",
            data_schema=vol.Schema(
                {vol.Required(CONF_SERVER): vol.In(available_servers)}
            ),
            errors={},
        )

    async def async_step_discovery(self, discovery_info):
        """Set default host and port from discovery."""
        if self._async_current_entries() or self._async_in_progress():
            # Skip discovery if a config already exists or is in progress.
            return self.async_abort(reason="already_configured")

        json_file = self.hass.config.path(PLEX_CONFIG_FILE)
        file_config = await self.hass.async_add_executor_job(load_json, json_file)

        if file_config:
            host_and_port, host_config = file_config.popitem()
            prefix = "https" if host_config[CONF_SSL] else "http"

            server_config = {
                CONF_URL: f"{prefix}://{host_and_port}",
                CONF_TOKEN: host_config[CONF_TOKEN],
                CONF_VERIFY_SSL: host_config["verify"],
            }
            _LOGGER.info("Imported legacy config, file can be removed: %s", json_file)
            return await self.async_step_server_validate(server_config)

        return await self.async_step_user()

    async def async_step_import(self, import_config):
        """Import from Plex configuration."""
        _LOGGER.debug("Imported Plex configuration")
        return await self.async_step_server_validate(import_config)
