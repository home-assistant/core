"""Config flow for Plex."""
import logging
import plexapi.exceptions
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
    CONF_VERIFY_SSL,
)

from .const import (
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLEX_SERVER_CONFIG,
)

_LOGGER = logging.getLogger(__package__)


@config_entries.HANDLERS.register(DOMAIN)
class PlexFlowHandler(config_entries.ConfigFlow):
    """Handle a Plex config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Plex flow."""
        self.config = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        for entry in self._async_current_entries():
            if PLEX_SERVER_CONFIG in entry.data:
                return self.async_abort(reason="already_configured")

        if user_input is not None:
            self.config = user_input

            try:
                token = self.config.get(CONF_TOKEN)
                if token is None:
                    raise plexapi.exceptions.Unauthorized

                plex_url = "{}://{}:{}".format(
                    "https" if self.config.get(CONF_SSL) else "http",
                    self.config[CONF_HOST],
                    self.config[CONF_PORT],
                )

                cert_session = None
                if not self.config[CONF_VERIFY_SSL]:
                    cert_session = Session()
                    cert_session.verify = False

                PlexServer(plex_url, token, cert_session)

                data = {PLEX_SERVER_CONFIG: self.config}

                return self.async_create_entry(title=self.config[CONF_HOST], data=data)

            except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized):
                errors["base"] = "faulty_credentials"
            except (plexapi.exceptions.NotFound, requests.exceptions.ConnectionError):
                errors["base"] = "not_found"
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.error("Unknown error connecting to %s: %s", plex_url, error)
                return self.async_abort(reason="unknown")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self.config.get(CONF_HOST)): str,
                vol.Optional(
                    CONF_PORT, default=self.config.get(CONF_PORT, DEFAULT_PORT)
                ): int,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
                vol.Required(CONF_TOKEN): str,
                vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_discovery(self, discovery_info):
        """Set default host and port from discovery."""
        config = {
            CONF_HOST: discovery_info.get("host"),
            CONF_PORT: int(discovery_info.get("port")),
            CONF_TOKEN: None,
            CONF_SSL: DEFAULT_SSL,
            CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
        }
        return await self.async_step_user(user_input=config)

    async def async_step_import(self, import_config):
        """Import from legacy Plex file config."""
        host_and_port, host_config = import_config.popitem()
        host, port = host_and_port.split(":")
        token = host_config["token"]
        try:
            has_ssl = host_config["ssl"]
        except KeyError:
            has_ssl = False
        try:
            verify_ssl = host_config["verify"]
        except KeyError:
            verify_ssl = True

        config = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_TOKEN: token,
            CONF_SSL: has_ssl,
            CONF_VERIFY_SSL: verify_ssl,
        }

        _LOGGER.info("Imported Plex configuration from legacy config file")
        return await self.async_step_user(user_input=config)
