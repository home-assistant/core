"""Config flow for Plex."""
import logging
import plexapi.exceptions
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from requests import Session
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from .const import (
    CONF_SERVER,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLEX_SERVER_CONFIG,
    TITLE_TEMPLATE,
)
from .errors import ConfigNotReady, NoServersFound, ServerNotSpecified, TokenMissing
from .server import setup_plex_server

_LOGGER = logging.getLogger(__package__)


@config_entries.HANDLERS.register(DOMAIN)
class PlexFlowHandler(config_entries.ConfigFlow):
    """Handle a Plex config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Plex flow."""
        self.current_login = {}
        self.discovery_info = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        for entry in self._async_current_entries():
            if PLEX_SERVER_CONFIG in entry.data:
                return self.async_abort(reason="already_configured")

        if user_input is not None:
            if user_input.get("manual_setup"):
                data_schema = vol.Schema(
                    {
                        vol.Required(
                            CONF_HOST, default=self.discovery_info.get(CONF_HOST)
                        ): str,
                        vol.Required(
                            CONF_PORT,
                            default=int(
                                self.discovery_info.get(CONF_PORT, DEFAULT_PORT)
                            ),
                        ): int,
                        vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
                        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
                    }
                )
                return self.async_show_form(
                    step_id="build_url", data_schema=data_schema, errors={}
                )

            
            plex_url = user_input.get(CONF_URL)
            token = user_input.get(CONF_TOKEN)
            username = user_input.get(CONF_USERNAME)
            server_name = user_input.get(CONF_SERVER)

            data = {}

            try:
                if (username is None) and (plex_url is None):
                    raise ConfigNotReady

                plex_server = setup_plex_server(user_input)

                if username:
                    if token is None:
                        self.current_login = {
                            CONF_USERNAME: username,
                            CONF_SERVER: server_name
                        }
                        raise TokenMissing

                    if not server_name:
                        server_name = plex_server.friendlyName

                    title = TITLE_TEMPLATE.format(server_name, account.username)
                    data = {
                        CONF_USERNAME: username,
                        CONF_TOKEN: token,
                        CONF_SERVER: server_name
                    }
                else:
                    self.current_login = {
                        CONF_URL: plex_url,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]
                    }
                    title = TITLE_TEMPLATE.format(plex_url, "Direct")
                    data = {
                        CONF_URL: plex_url,
                        CONF_TOKEN: token,
                        CONF_VERIFY_SSL: verify_ssl,
                    }

                return self.async_create_entry(
                    title=title, data={PLEX_SERVER_CONFIG: data}
                )

            except ConfigNotReady:
                errors["base"] = "config_not_ready"
            except NoServersFound:
                errors["base"] = "no_servers"
            except ServerNotSpecified:
                errors["base"] = "server_not_specified"
            except (
                plexapi.exceptions.BadRequest,
                plexapi.exceptions.Unauthorized,
                TokenMissing,
            ):
                errors["base"] = "faulty_credentials"
                if token is None:
                    return self.async_show_form(
                        step_id="token",
                        data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
                        errors={},
                    )
            except (plexapi.exceptions.NotFound, requests.exceptions.ConnectionError):
                errors["base"] = "not_found"
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.error("Unknown error connecting to Plex server: %s", error)
                return self.async_abort(reason="unknown")

        data_schema = vol.Schema(
            {vol.Optional(CONF_USERNAME): str, vol.Optional("manual_setup"): bool}
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_token(self, user_input=None):
        """Get auth token from user if needed."""
        if user_input is None:
            return await self.async_step_user()

        config = self.current_login
        config[CONF_TOKEN] = user_input.get(CONF_TOKEN)
        return await self.async_step_user(user_input=config)

    async def async_step_build_url(self, user_input=None):
        """Build URL from components."""
        if user_input is None:
            return await self.async_step_user()

        host = user_input.pop(CONF_HOST)
        port = user_input.pop(CONF_PORT)
        user_input[CONF_URL] = "{}://{}:{}".format(
            "https" if user_input.get(CONF_SSL) else "http", host, port
        )
        return await self.async_step_user(user_input=user_input)

    async def async_step_discovery(self, discovery_info):
        """Set default host and port from discovery."""
        self.discovery_info = discovery_info
        return await self.async_step_user()

    async def async_step_import(self, import_config):
        """Import from legacy Plex file config."""
        host_and_port, host_config = import_config.popitem()
        prefix = "https" if host_config[CONF_SSL] else "http"
        plex_url = "{}://{}".format(prefix, host_and_port)

        config = {
            CONF_URL: plex_url,
            CONF_TOKEN: host_config[CONF_TOKEN],
            CONF_VERIFY_SSL: host_config["verify"],
        }

        _LOGGER.info("Imported Plex configuration from legacy config file")
        return await self.async_step_user(user_input=config)
