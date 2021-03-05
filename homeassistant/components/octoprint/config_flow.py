"""Config flow for OctoPrint integration."""
import logging
from urllib.parse import urlsplit

from pyoctoprintapi import ApiError, OctoprintClient
import requests
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


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_PATH, default="/"): cv.string,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)


def _schema_with_defaults(host=None, port=80, path="/"):
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_HOST, default=host): cv.string,
            vol.Optional(CONF_PORT, default=port): cv.port,
            vol.Optional(CONF_PATH, default=path): cv.string,
            vol.Optional(CONF_SSL, default=False): cv.boolean,
        },
        extra=vol.ALLOW_EXTRA,
    )


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    session = async_get_clientsession(hass)
    octoprint = OctoprintClient(
        data[CONF_HOST], session, data[CONF_PORT], data[CONF_SSL], data[CONF_PATH]
    )

    if CONF_API_KEY not in data:
        try:
            data[CONF_API_KEY] = await octoprint.request_app_key(
                "Home Assistant", data[CONF_USERNAME], 30
            )
        except ApiError as ex:
            _LOGGER.error("Failed to retrieve application key: %s", ex)
            raise InvalidAuth from ex

    octoprint.set_api_key(data[CONF_API_KEY])
    await validate_connection(octoprint)

    discovery = await octoprint.get_discovery_info()
    uuid = None
    if discovery:
        uuid = discovery.upnp_uuid

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_HOST], "uuid": uuid}


async def validate_connection(octoprint: OctoprintClient):
    """Validate the connection to the printer."""
    try:
        await octoprint.get_server_info()
    except requests.exceptions.RequestException as conn_err:
        _LOGGER.error("Error setting up OctoPrint API: %r", conn_err)
        raise CannotConnect from conn_err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OctoPrint."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Handle a config flow for OctoPrint."""
        self.discovery_schema = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            data = self.discovery_schema or _schema_with_defaults()
            return self.async_show_form(step_id="user", data_schema=data)

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
            if info["uuid"]:
                await self.async_set_unique_id(info["uuid"])
                self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(self, discovery_info):
        """Handle discovery flow."""
        uuid = discovery_info["properties"]["uuid"]
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            CONF_HOST: discovery_info[CONF_HOST],
        }

        self.discovery_schema = _schema_with_defaults(
            discovery_info[CONF_HOST],
            discovery_info[CONF_PORT],
            discovery_info["properties"][CONF_PATH],
        )

        return await self.async_step_user()

    async def async_step_ssdp(self, discovery_info):
        """Handle ssdp discovery flow."""
        uuid = discovery_info["UDN"][5:]
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        url = urlsplit(discovery_info["presentationURL"])
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            CONF_HOST: url.hostname,
        }

        self.discovery_schema = _schema_with_defaults(
            url.hostname,
            url.port,
        )

        return await self.async_step_user()


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
