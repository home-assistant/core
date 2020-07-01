"""Config flow for Plex."""
import copy
import logging

from aiohttp import web_response
import plexapi.exceptions
from plexapi.gdm import GDM
from plexauth import PlexAuth
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import get_url

from .const import (  # pylint: disable=unused-import
    AUTH_CALLBACK_NAME,
    AUTH_CALLBACK_PATH,
    AUTOMATIC_SETUP_STRING,
    CONF_IGNORE_NEW_SHARED_USERS,
    CONF_IGNORE_PLEX_WEB_CLIENTS,
    CONF_MONITORED_USERS,
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    CONF_USE_EPISODE_ART,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MANUAL_SETUP_STRING,
    PLEX_SERVER_CONFIG,
    SERVERS,
    X_PLEX_DEVICE_NAME,
    X_PLEX_PLATFORM,
    X_PLEX_PRODUCT,
    X_PLEX_VERSION,
)
from .errors import NoServersFound, ServerNotSpecified
from .server import PlexServer

_LOGGER = logging.getLogger(__package__)


@callback
def configured_servers(hass):
    """Return a set of the configured Plex servers."""
    return {
        entry.data[CONF_SERVER_IDENTIFIER]
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


async def async_discover(hass):
    """Scan for available Plex servers."""
    gdm = GDM()
    await hass.async_add_executor_job(gdm.scan)
    for server_data in gdm.entries:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=server_data,
        )


class PlexFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Plex config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PlexOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the Plex flow."""
        self.current_login = {}
        self.available_servers = None
        self.plexauth = None
        self.token = None
        self.client_id = None
        self._manual = False

    async def async_step_user(self, user_input=None, errors=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return await self.async_step_plex_website_auth()
        if self.show_advanced_options:
            return await self.async_step_user_advanced(errors=errors)
        return self.async_show_form(step_id="user", errors=errors)

    async def async_step_user_advanced(self, user_input=None, errors=None):
        """Handle an advanced mode flow initialized by the user."""
        if user_input is not None:
            if user_input.get("setup_method") == MANUAL_SETUP_STRING:
                self._manual = True
                return await self.async_step_manual_setup()
            return await self.async_step_plex_website_auth()

        data_schema = vol.Schema(
            {
                vol.Required("setup_method", default=AUTOMATIC_SETUP_STRING): vol.In(
                    [AUTOMATIC_SETUP_STRING, MANUAL_SETUP_STRING]
                )
            }
        )
        return self.async_show_form(
            step_id="user_advanced", data_schema=data_schema, errors=errors
        )

    async def async_step_manual_setup(self, user_input=None, errors=None):
        """Begin manual configuration."""
        if user_input is not None and errors is None:
            user_input.pop(CONF_URL, None)
            host = user_input.get(CONF_HOST)
            if host:
                port = user_input[CONF_PORT]
                prefix = "https" if user_input.get(CONF_SSL) else "http"
                user_input[CONF_URL] = f"{prefix}://{host}:{port}"
            elif CONF_TOKEN not in user_input:
                return await self.async_step_manual_setup(
                    user_input=user_input, errors={"base": "host_or_token"}
                )
            return await self.async_step_server_validate(user_input)

        previous_input = user_input or {}

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_HOST,
                    description={"suggested_value": previous_input.get(CONF_HOST)},
                ): str,
                vol.Required(
                    CONF_PORT, default=previous_input.get(CONF_PORT, DEFAULT_PORT)
                ): int,
                vol.Required(
                    CONF_SSL, default=previous_input.get(CONF_SSL, DEFAULT_SSL)
                ): bool,
                vol.Required(
                    CONF_VERIFY_SSL,
                    default=previous_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                ): bool,
                vol.Optional(
                    CONF_TOKEN,
                    description={"suggested_value": previous_input.get(CONF_TOKEN)},
                ): str,
            }
        )
        return self.async_show_form(
            step_id="manual_setup", data_schema=data_schema, errors=errors
        )

    async def async_step_server_validate(self, server_config):
        """Validate a provided configuration."""
        errors = {}
        self.current_login = server_config

        plex_server = PlexServer(self.hass, server_config)
        try:
            await self.hass.async_add_executor_job(plex_server.connect)

        except NoServersFound:
            _LOGGER.error("No servers linked to Plex account")
            errors["base"] = "no_servers"
        except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized):
            _LOGGER.error("Invalid credentials provided, config not created")
            errors[CONF_TOKEN] = "faulty_credentials"
        except requests.exceptions.SSLError as error:
            _LOGGER.error("SSL certificate error: [%s]", error)
            errors["base"] = "ssl_error"
        except (plexapi.exceptions.NotFound, requests.exceptions.ConnectionError):
            server_identifier = (
                server_config.get(CONF_URL) or plex_server.server_choice or "Unknown"
            )
            _LOGGER.error("Plex server could not be reached: %s", server_identifier)
            errors[CONF_HOST] = "not_found"

        except ServerNotSpecified as available_servers:
            self.available_servers = available_servers.args[0]
            return await self.async_step_select_server()

        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error connecting to Plex server: %s", error)
            return self.async_abort(reason="unknown")

        if errors:
            if self._manual:
                return await self.async_step_manual_setup(
                    user_input=server_config, errors=errors
                )
            return await self.async_step_user(errors=errors)

        server_id = plex_server.machine_identifier

        await self.async_set_unique_id(server_id)
        self._abort_if_unique_id_configured()

        url = plex_server.url_in_use
        token = server_config.get(CONF_TOKEN)

        entry_config = {CONF_URL: url}
        if self.client_id:
            entry_config[CONF_CLIENT_ID] = self.client_id
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

    async def async_step_integration_discovery(self, discovery_info):
        """Handle GDM discovery."""
        machine_identifier = discovery_info["data"]["Resource-Identifier"]
        await self.async_set_unique_id(machine_identifier)
        self._abort_if_unique_id_configured()
        host = f"{discovery_info['from'][0]}:{discovery_info['data']['Port']}"
        name = discovery_info["data"]["Name"]
        self.context["title_placeholders"] = {  # pylint: disable=no-member
            "host": host,
            "name": name,
        }
        return await self.async_step_user()

    async def async_step_plex_website_auth(self):
        """Begin external auth flow on Plex website."""
        self.hass.http.register_view(PlexAuthorizationCallbackView)
        payload = {
            "X-Plex-Device-Name": X_PLEX_DEVICE_NAME,
            "X-Plex-Version": X_PLEX_VERSION,
            "X-Plex-Product": X_PLEX_PRODUCT,
            "X-Plex-Device": self.hass.config.location_name,
            "X-Plex-Platform": X_PLEX_PLATFORM,
            "X-Plex-Model": "Plex OAuth",
        }
        session = async_get_clientsession(self.hass)
        self.plexauth = PlexAuth(payload, session)
        await self.plexauth.initiate_auth()
        forward_url = f"{get_url(self.hass)}{AUTH_CALLBACK_PATH}?flow_id={self.flow_id}"
        auth_url = self.plexauth.auth_url(forward_url)
        return self.async_external_step(step_id="obtain_token", url=auth_url)

    async def async_step_obtain_token(self, user_input=None):
        """Obtain token after external auth completed."""
        token = await self.plexauth.token(10)

        if not token:
            return self.async_external_step_done(next_step_id="timed_out")

        self.token = token
        self.client_id = self.plexauth.client_identifier
        return self.async_external_step_done(next_step_id="use_external_token")

    async def async_step_timed_out(self, user_input=None):
        """Abort flow when time expires."""
        return self.async_abort(reason="token_request_timeout")

    async def async_step_use_external_token(self, user_input=None):
        """Continue server validation with external token."""
        server_config = {CONF_TOKEN: self.token}
        return await self.async_step_server_validate(server_config)


class PlexOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Plex options."""

    def __init__(self, config_entry):
        """Initialize Plex options flow."""
        self.options = copy.deepcopy(dict(config_entry.options))
        self.server_id = config_entry.data[CONF_SERVER_IDENTIFIER]

    async def async_step_init(self, user_input=None):
        """Manage the Plex options."""
        return await self.async_step_plex_mp_settings()

    async def async_step_plex_mp_settings(self, user_input=None):
        """Manage the Plex media_player options."""
        plex_server = self.hass.data[DOMAIN][SERVERS][self.server_id]

        if user_input is not None:
            self.options[MP_DOMAIN][CONF_USE_EPISODE_ART] = user_input[
                CONF_USE_EPISODE_ART
            ]
            self.options[MP_DOMAIN][CONF_IGNORE_NEW_SHARED_USERS] = user_input[
                CONF_IGNORE_NEW_SHARED_USERS
            ]
            self.options[MP_DOMAIN][CONF_IGNORE_PLEX_WEB_CLIENTS] = user_input[
                CONF_IGNORE_PLEX_WEB_CLIENTS
            ]

            account_data = {
                user: {"enabled": bool(user in user_input[CONF_MONITORED_USERS])}
                for user in plex_server.accounts
            }

            self.options[MP_DOMAIN][CONF_MONITORED_USERS] = account_data

            return self.async_create_entry(title="", data=self.options)

        available_accounts = {name: name for name in plex_server.accounts}
        available_accounts[plex_server.owner] += " [Owner]"

        default_accounts = plex_server.accounts
        known_accounts = set(plex_server.option_monitored_users)
        if known_accounts:
            default_accounts = {
                user
                for user in plex_server.option_monitored_users
                if plex_server.option_monitored_users[user]["enabled"]
            }
            for user in plex_server.accounts:
                if user not in known_accounts:
                    available_accounts[user] += " [New]"

        if not plex_server.option_ignore_new_shared_users:
            for new_user in plex_server.accounts - known_accounts:
                default_accounts.add(new_user)

        return self.async_show_form(
            step_id="plex_mp_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USE_EPISODE_ART,
                        default=plex_server.option_use_episode_art,
                    ): bool,
                    vol.Optional(
                        CONF_MONITORED_USERS, default=default_accounts
                    ): cv.multi_select(available_accounts),
                    vol.Required(
                        CONF_IGNORE_NEW_SHARED_USERS,
                        default=plex_server.option_ignore_new_shared_users,
                    ): bool,
                    vol.Required(
                        CONF_IGNORE_PLEX_WEB_CLIENTS,
                        default=plex_server.option_ignore_plexweb_clients,
                    ): bool,
                }
            ),
        )


class PlexAuthorizationCallbackView(HomeAssistantView):
    """Handle callback from external auth."""

    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME
    requires_auth = False

    async def get(self, request):
        """Receive authorization confirmation."""
        hass = request.app["hass"]
        await hass.config_entries.flow.async_configure(
            flow_id=request.query["flow_id"], user_input=None
        )

        return web_response.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>Success! This window can be closed",
        )
