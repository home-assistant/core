"""Config flow to configure the Netgear integration."""

from __future__ import annotations

import logging
from typing import cast
from urllib.parse import urlparse

from pynetgear import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_USER
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.util.network import is_ipv4_address

from .const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_NAME,
    DOMAIN,
    MODELS_PORT_80,
    MODELS_PORT_5555,
    PORT_80,
    PORT_5555,
)
from .errors import CannotLoginException
from .router import get_api

_LOGGER = logging.getLogger(__name__)


def _discovery_schema_with_defaults(discovery_info):
    return vol.Schema(_ordered_shared_schema(discovery_info))


def _user_schema_with_defaults(user_input):
    user_schema = {vol.Optional(CONF_HOST, default=user_input.get(CONF_HOST, "")): str}
    user_schema.update(_ordered_shared_schema(user_input))

    return vol.Schema(user_schema)


def _ordered_shared_schema(schema_input):
    return {
        vol.Optional(CONF_USERNAME, default=schema_input.get(CONF_USERNAME, "")): str,
        vol.Required(CONF_PASSWORD, default=schema_input.get(CONF_PASSWORD, "")): str,
    }


class OptionsFlowHandler(OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
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


class NetgearFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
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
        config_entry: ConfigEntry,
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

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Initialize flow from ssdp."""
        updated_data: dict[str, str | int | bool] = {}

        device_url = urlparse(discovery_info.ssdp_location)
        if hostname := device_url.hostname:
            hostname = cast(str, hostname)
            updated_data[CONF_HOST] = hostname

        if not is_ipv4_address(str(hostname)):
            return self.async_abort(reason="not_ipv4_address")

        _LOGGER.debug("Netgear ssdp discovery info: %s", discovery_info)

        if ssdp.ATTR_UPNP_SERIAL not in discovery_info.upnp:
            return self.async_abort(reason="no_serial")

        await self.async_set_unique_id(discovery_info.upnp[ssdp.ATTR_UPNP_SERIAL])
        self._abort_if_unique_id_configured(updates=updated_data)

        if device_url.scheme == "https":
            updated_data[CONF_SSL] = True
        else:
            updated_data[CONF_SSL] = False

        updated_data[CONF_PORT] = DEFAULT_PORT
        for model in MODELS_PORT_80:
            if discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NUMBER, "").startswith(
                model
            ) or discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME, "").startswith(
                model
            ):
                updated_data[CONF_PORT] = PORT_80
        for model in MODELS_PORT_5555:
            if discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NUMBER, "").startswith(
                model
            ) or discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME, "").startswith(
                model
            ):
                updated_data[CONF_PORT] = PORT_5555
                updated_data[CONF_SSL] = True

        self.placeholders.update(updated_data)
        self.discovered = True

        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form()

        host = user_input.get(CONF_HOST, self.placeholders[CONF_HOST])
        port = self.placeholders[CONF_PORT]
        ssl = self.placeholders[CONF_SSL]
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
            return await self._show_setup_form(user_input, errors)

        config_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_HOST: host,
            CONF_PORT: api.port,
            CONF_SSL: api.ssl,
        }

        # Check if already configured
        info = await self.hass.async_add_executor_job(api.get_info)
        if info is None:
            errors["base"] = "info"
            return await self._show_setup_form(user_input, errors)

        await self.async_set_unique_id(info["SerialNumber"], raise_on_progress=False)
        self._abort_if_unique_id_configured(updates=config_data)

        if info.get("ModelName") is not None and info.get("DeviceName") is not None:
            name = f"{info['ModelName']} - {info['DeviceName']}"
        else:
            name = info.get("ModelName", DEFAULT_NAME)

        return self.async_create_entry(
            title=name,
            data=config_data,
        )
