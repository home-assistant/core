"""Config flow to configure the Netgear integration."""
import asyncio
import logging

from pynetgear import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_USER, Netgear, autodetect_url
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


def _discovery_schema_with_defaults(discovery_info):
    return vol.Schema(_ordered_shared_schema(discovery_info))


def _user_schema_with_defaults(user_input):
    user_schema = {
        vol.Optional(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
        vol.Optional(CONF_PORT, default=user_input.get(CONF_PORT, "")): int,
        vol.Optional(CONF_SSL, default=user_input.get(CONF_SSL, False)): bool,
    }
    user_schema.update(_ordered_shared_schema(user_input))

    return vol.Schema(user_schema)


def _ordered_shared_schema(schema_input):
    return {
        vol.Optional(CONF_USERNAME, default=schema_input.get(CONF_USERNAME, "")): str,
        vol.Required(CONF_PASSWORD, default=schema_input.get(CONF_PASSWORD, "")): str,
    }


class NetgearFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the netgear config flow."""
        self.discovered_conf = {}
        self.placeholders = {
            CONF_NAME: "",
            CONF_HOST: DEFAULT_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: DEFAULT_USER,
        }

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""
        if not user_input:
            user_input = {}

        if self.discovered_conf.get(CONF_URL):
            user_input.update(self.discovered_conf)
            step_id = "link"
            data_schema = _discovery_schema_with_defaults(user_input)
        else:
            step_id = "user"
            data_schema = _user_schema_with_defaults(user_input)

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors or {},
            description_placeholders=self.placeholders or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if self.source == config_entries.SOURCE_IMPORT:
            if not user_input.get(CONF_HOST):
                url = await self.hass.async_add_executor_job(autodetect_url)
                self.placeholders[CONF_URL] = url

        elif not self.discovered_conf.get(CONF_URL):
            return await self.async_step_discover()

        if not user_input:
            return await self._show_setup_form(user_input, errors)

        url = self.placeholders.get(CONF_URL)
        host = user_input.get(CONF_HOST)
        port = user_input.get(CONF_PORT)
        ssl = user_input.get(CONF_SSL)
        username = user_input.get(CONF_USERNAME)
        password = user_input[CONF_PASSWORD]

        try:
            # Open connection and check authentication
            api = await self.hass.async_add_executor_job(
                Netgear, password, host, username, port, ssl, url
            )
            if not await self.hass.async_add_executor_job(api.login):
                raise InvalidAuth

            # Get device infos to check if already configured
            infos = await self.hass.async_add_executor_job(api.get_info)

        except OSError:
            _LOGGER.error("Error connecting to the Netgear router at %s", host)
            errors["base"] = "connection"
        except InvalidAuth:
            errors[CONF_USERNAME] = "login"
        except Exception as exp:  # pylint: disable=broad-except
            _LOGGER.error(exp)
            errors[CONF_USERNAME] = "unknown"

        await self.async_set_unique_id(infos["SerialNumber"])
        self._abort_if_unique_id_configured()

        if errors:
            return await self._show_setup_form(user_input, errors)

        return self.async_create_entry(
            title=f"{infos['ModelName']} - {infos['DeviceName']}", data=user_input,
        )

    async def async_step_discover(self, user_input=None):
        """Discover host, port and SSL."""
        if user_input is None:
            return self.async_show_form(step_id="discover")

        url = await self.hass.async_add_executor_job(autodetect_url)
        self.discovered_conf[CONF_URL] = url
        self.placeholders[CONF_URL] = url
        return await self.async_step_user()

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered device."""
        # brief delay to allow processing the import step first
        await asyncio.sleep(20)

        await self.async_set_unique_id(discovery_info[ssdp.ATTR_UPNP_SERIAL])
        self._abort_if_unique_id_configured()

        friendly_name = discovery_info[ssdp.ATTR_UPNP_MODEL_NUMBER]
        self.discovered_conf[CONF_NAME] = friendly_name
        self.placeholders[CONF_NAME] = friendly_name
        return await self.async_step_user()

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    async def async_step_link(self, user_input):
        """Link a config entry from discovery."""
        return await self.async_step_user(user_input)


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
