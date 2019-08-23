"""Config flow for Plex."""
import logging
import plexapi.exceptions
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback

from .const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    CONF_ENABLE_MEDIA_PLAYER,
    CONF_ENABLE_SENSOR,
    CONF_USE_EPISODE_ART,
    CONF_SHOW_ALL_CONTROLS,
    CONF_REMOVE_UNAVAILABLE_CLIENTS,
    CONF_CLIENT_REMOVE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLEX_SERVER_CONFIG,
)
from .errors import ConfigNotReady, NoServersFound, ServerNotSpecified, TokenMissing
from .server import setup_plex_server

_LOGGER = logging.getLogger(__package__)


class PlexFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Plex config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PlexOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the Plex flow."""
        self.current_login = {}
        self.discovery_info = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

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

            url = user_input.get(CONF_URL)
            token = user_input.get(CONF_TOKEN)
            username = user_input.get(CONF_USERNAME)
            server_name = user_input.get(CONF_SERVER)

            data = {}

            try:
                if (username is None) and (url is None):
                    raise ConfigNotReady

                self.current_login = user_input

                if username:
                    if token is None:
                        raise TokenMissing

                    data = {
                        CONF_USERNAME: username,
                        CONF_TOKEN: token,
                        CONF_SERVER: server_name,
                    }
                else:
                    data = {
                        CONF_URL: url,
                        CONF_TOKEN: token,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    }

                plex_server = setup_plex_server(user_input)

                server_id = plex_server.machineIdentifier

                for entry in self._async_current_entries():
                    if entry.data[CONF_SERVER_IDENTIFIER] == server_id:
                        return self.async_abort(reason="already_configured")

                title = "{} ({})".format(
                    plex_server.friendlyName, username if username else "Direct"
                )

                if username and not server_name:
                    data[CONF_SERVER] = plex_server.friendlyName

                return self.async_create_entry(
                    title=title,
                    data={CONF_SERVER_IDENTIFIER: server_id, PLEX_SERVER_CONFIG: data},
                )

            except ConfigNotReady:
                errors["base"] = "config_not_ready"
            except NoServersFound:
                errors["base"] = "no_servers"
            except ServerNotSpecified as available_servers:
                return self.async_show_form(
                    step_id="select_server",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_SERVER): vol.In(available_servers[0])}
                    ),
                    errors={},
                )
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

    async def async_step_select_server(self, user_input=None):
        """Use selected Plex server."""
        if user_input is None:
            return await self.async_step_user()

        config = self.current_login
        config[CONF_SERVER] = user_input.get(CONF_SERVER)
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

    async def async_step_import_media_player(self, import_config):
        """Import from Plex media_player file config.

        Legacy.
        """
        if self._async_in_progress():
            return self.async_abort(reason="already_in_progress")

        host_and_port, host_config = import_config.popitem()
        prefix = "https" if host_config[CONF_SSL] else "http"
        url = "{}://{}".format(prefix, host_and_port)

        config = {
            CONF_URL: url,
            CONF_TOKEN: host_config[CONF_TOKEN],
            CONF_VERIFY_SSL: host_config["verify"],
        }

        _LOGGER.info("Imported Plex configuration from legacy config file")
        return await self.async_step_user(user_input=config)


class PlexOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Plex options."""

    def __init__(self, config_entry):
        """Initialize Plex options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the Plex options."""
        return await self.async_step_plex_platforms()

    async def async_step_plex_platforms(self, user_input=None):
        """Choose Plex platforms to enable."""
        if user_input is not None:
            self.options[CONF_ENABLE_MEDIA_PLAYER] = user_input[
                CONF_ENABLE_MEDIA_PLAYER
            ]
            self.options[CONF_ENABLE_SENSOR] = user_input[CONF_ENABLE_SENSOR]
            if user_input[CONF_ENABLE_MEDIA_PLAYER]:
                return self.async_show_form(
                    step_id="plex_mp_settings",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_USE_EPISODE_ART,
                                default=self.options[CONF_USE_EPISODE_ART],
                            ): bool,
                            vol.Required(
                                CONF_SHOW_ALL_CONTROLS,
                                default=self.options[CONF_SHOW_ALL_CONTROLS],
                            ): bool,
                            vol.Required(
                                CONF_REMOVE_UNAVAILABLE_CLIENTS,
                                default=self.options[CONF_REMOVE_UNAVAILABLE_CLIENTS],
                            ): bool,
                            vol.Required(
                                CONF_CLIENT_REMOVE_INTERVAL,
                                default=self.options[CONF_CLIENT_REMOVE_INTERVAL],
                            ): vol.All(int, vol.Range(min=1)),
                        }
                    ),
                )

            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="plex_platforms",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_MEDIA_PLAYER,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_MEDIA_PLAYER, True
                        ),
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_SENSOR,
                        default=self.config_entry.options.get(CONF_ENABLE_SENSOR, True),
                    ): bool,
                }
            ),
        )

    async def async_step_plex_mp_settings(self, user_input=None):
        """Manage the Plex media_player options."""
        if user_input is not None:
            if MP_DOMAIN not in self.options:
                self.options[MP_DOMAIN] = {}

            self.options[MP_DOMAIN][CONF_USE_EPISODE_ART] = user_input[
                CONF_USE_EPISODE_ART
            ]
            self.options[MP_DOMAIN][CONF_SHOW_ALL_CONTROLS] = user_input[
                CONF_SHOW_ALL_CONTROLS
            ]
            self.options[MP_DOMAIN][CONF_REMOVE_UNAVAILABLE_CLIENTS] = user_input[
                CONF_REMOVE_UNAVAILABLE_CLIENTS
            ]
            self.options[MP_DOMAIN][CONF_CLIENT_REMOVE_INTERVAL] = user_input[
                CONF_CLIENT_REMOVE_INTERVAL
            ]

        return self.async_create_entry(title="", data=self.options)
