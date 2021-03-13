"""Config flow for OctoPrint integration."""
import logging
from urllib.parse import urlsplit

from pyoctoprintapi import ApiError, OctoprintClient, OctoprintException
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(username="", host=None, port=80, path="/", ssl=False):
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): cv.string,
            vol.Required(CONF_HOST, default=host): cv.string,
            vol.Optional(CONF_PORT, default=port): cv.port,
            vol.Optional(CONF_PATH, default=path): cv.string,
            vol.Optional(CONF_SSL, default=ssl): cv.boolean,
        },
        extra=vol.ALLOW_EXTRA,
    )


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    session = async_get_clientsession(hass)
    octoprint = OctoprintClient(
        data[CONF_HOST], session, data[CONF_PORT], data[CONF_SSL], data[CONF_PATH]
    )
    octoprint.set_api_key(data[CONF_API_KEY])

    try:
        discovery = await octoprint.get_discovery_info()
    except ApiError as conn_err:
        _LOGGER.error("Error setting up OctoPrint API: %r", conn_err)
        raise CannotConnect from conn_err

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_HOST], "uuid": discovery.upnp_uuid}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OctoPrint."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    api_key_task = None

    def __init__(self):
        """Handle a config flow for OctoPrint."""
        self.discovery_schema = None
        self.user_input = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            data = self.discovery_schema or _schema_with_defaults()
            return self.async_show_form(step_id="user", data_schema=data)

        self.user_input = user_input
        if CONF_API_KEY in user_input:
            return await self.async_step_finish(user_input)

        self.api_key_task = None
        return await self.async_step_get_api_key(user_input)

    async def async_step_get_api_key(self, user_input=None):
        """Get an Application Api Key."""
        if not self.api_key_task:
            self.api_key_task = self.hass.async_create_task(self._async_get_auth_key())
            return self.async_show_progress(
                step_id="get_api_key", progress_action="get_api_key"
            )

        try:
            await self.api_key_task
        except OctoprintException as err:
            _LOGGER.error("Failed to get an application key : %s", err)
            return self.async_show_progress_done(next_step_id="auth_failed")

        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_finish(self, user_input=None):
        """Finish the configuration setup."""
        user_input = user_input or self.user_input
        error = None

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            error = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            error = "unknown"
        else:
            await self.async_set_unique_id(info["uuid"], raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)

        return self._create_setup_failure(user_input, error)

    async def async_step_auth_failed(self, user_input):
        """Handle api fetch failure."""
        return self._create_setup_failure(self.user_input, "auth_failed")

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(self, discovery_info):
        """Handle discovery flow."""
        uuid = discovery_info["properties"]["uuid"]
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {
            CONF_HOST: discovery_info[CONF_HOST],
        }

        self.discovery_schema = _schema_with_defaults(
            host=discovery_info[CONF_HOST],
            port=discovery_info[CONF_PORT],
            path=discovery_info["properties"][CONF_PATH],
        )

        return await self.async_step_user()

    async def async_step_ssdp(self, discovery_info):
        """Handle ssdp discovery flow."""
        uuid = discovery_info["UDN"][5:]
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        url = urlsplit(discovery_info["presentationURL"])
        self.context["title_placeholders"] = {
            CONF_HOST: url.hostname,
        }

        self.discovery_schema = _schema_with_defaults(
            host=url.hostname,
            port=url.port,
        )

        return await self.async_step_user()

    async def _async_get_auth_key(self):
        """Get application api key."""
        session = async_get_clientsession(self.hass)
        octoprint = OctoprintClient(
            self.user_input[CONF_HOST],
            session,
            self.user_input[CONF_PORT],
            self.user_input[CONF_SSL],
            self.user_input[CONF_PATH],
        )

        try:
            self.user_input[CONF_API_KEY] = await octoprint.request_app_key(
                "Home Assistant", self.user_input[CONF_USERNAME], 30
            )
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_configure(
                    flow_id=self.flow_id, user_input=self.user_input
                )
            )

    def _create_setup_failure(self, user_input: dict, error_code: str):
        data_schema = _schema_with_defaults(
            username=user_input[CONF_USERNAME],
            host=user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            path=user_input[CONF_PATH],
            ssl=user_input[CONF_SSL],
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors={"base": error_code}
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
