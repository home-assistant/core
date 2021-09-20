"""Config flow to configure the Netgear integration."""
from urllib.parse import urlparse

from pynetgear import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_USER
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME, DEFAULT_NAME, DOMAIN
from .errors import CannotLoginException
from .router import get_api


def _discovery_schema_with_defaults(discovery_info):
    return vol.Schema(_ordered_shared_schema(discovery_info))


def _user_schema_with_defaults(user_input):
    user_schema = {
        vol.Optional(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
        vol.Optional(CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)): int,
        vol.Optional(CONF_SSL, default=user_input.get(CONF_SSL, False)): bool,
    }
    user_schema.update(_ordered_shared_schema(user_input))

    return vol.Schema(user_schema)


def _ordered_shared_schema(schema_input):
    return {
        vol.Optional(CONF_USERNAME, default=schema_input.get(CONF_USERNAME, "")): str,
        vol.Required(CONF_PASSWORD, default=schema_input.get(CONF_PASSWORD, "")): str,
    }


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        settings_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CONSIDER_HOME,
                    default=self.config_entry.options.get(
                        CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
                    ),
                ): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=settings_schema)


class NetgearFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the netgear config flow."""
        self.placeholders = {
            CONF_HOST: DEFAULT_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: DEFAULT_USER,
            CONF_SSL: False,
        }
        self.discovered = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""
        if not user_input:
            user_input = {}

        if self.discovered:
            data_schema = _discovery_schema_with_defaults(user_input)
        else:
            data_schema = _user_schema_with_defaults(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors or {},
            description_placeholders=self.placeholders,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    async def async_step_ssdp(self, discovery_info: dict) -> FlowResult:
        """Initialize flow from ssdp."""
        updated_data = {}

        device_url = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION])
        if device_url.hostname:
            updated_data[CONF_HOST] = device_url.hostname
        if device_url.port:
            updated_data[CONF_PORT] = device_url.port
        if device_url.scheme == "https":
            updated_data[CONF_SSL] = True
        else:
            updated_data[CONF_SSL] = False

        await self.async_set_unique_id(discovery_info[ssdp.ATTR_UPNP_SERIAL])
        self._abort_if_unique_id_configured(updates=updated_data)
        self.placeholders.update(updated_data)
        self.discovered = True

        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form()

        host = user_input.get(CONF_HOST, self.placeholders[CONF_HOST])
        port = user_input.get(CONF_PORT, self.placeholders[CONF_PORT])
        ssl = user_input.get(CONF_SSL, self.placeholders[CONF_SSL])
        username = user_input.get(CONF_USERNAME, self.placeholders[CONF_USERNAME])
        password = user_input[CONF_PASSWORD]
        if not username:
            username = self.placeholders[CONF_USERNAME]

        # Open connection and check authentication
        try:
            api = await self.hass.async_add_executor_job(
                get_api, password, host, username, port, ssl
            )
        except CannotLoginException:
            errors["base"] = "config"

        if errors:
            return await self._show_setup_form(user_input, errors)

        # Check if already configured
        info = await self.hass.async_add_executor_job(api.get_info)
        await self.async_set_unique_id(info["SerialNumber"], raise_on_progress=False)
        self._abort_if_unique_id_configured()

        config_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SSL: ssl,
        }

        if info.get("ModelName") is not None and info.get("DeviceName") is not None:
            name = f"{info['ModelName']} - {info['DeviceName']}"
        else:
            name = info.get("ModelName", DEFAULT_NAME)

        return self.async_create_entry(
            title=name,
            data=config_data,
        )
