"""Config flow to configure the integration of a LG TV running on NetCast 3 or 4."""
from __future__ import annotations

from typing import Any

from pylgnetcast import AccessTokenError, LgNetCastClient, LgNetCastError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.util.network import is_host_valid

# from . import LgTVDevice
from .const import DOMAIN


class LgNetCastConfigFLow(config_entries.ConfigFlow, domain=DOMAIN):
    """Implementation of the LG NetCast config flow."""

    VERSION = 1

    client: LgNetCastClient

    def __init__(self) -> None:
        """Initialize NetCast config flow."""
        self.device_config: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LgNetCastOptionsFlow:
        """Return options flow for LG NetCast."""
        return LgNetCastOptionsFlow(config_entry)

    async def async_init_device(self) -> FlowResult:
        """Initialize and create NetCast device from config."""
        host = self.device_config[CONF_HOST]
        access_token = self.device_config[CONF_ACCESS_TOKEN]
        name = self.device_config[CONF_NAME]

        self.client = LgNetCastClient(host, access_token)
        await self.hass.async_add_executor_job(self.client.query_data, "cur_channel")

        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=name, data=self.device_config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial config flow step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            host = user_input[CONF_HOST]
            if is_host_valid(host):
                self.client = LgNetCastClient(host, "")
                self.device_config[CONF_NAME] = name
                self.device_config[CONF_HOST] = host

                return await self.async_step_authorize()

            errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="LG TV Remote"): str,
                    vol.Required(CONF_HOST, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for the access token for the NetCast device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.device_config[CONF_ACCESS_TOKEN] = user_input[CONF_ACCESS_TOKEN]
            try:
                return await self.async_init_device()
            except AccessTokenError:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"
            except LgNetCastError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN, default=""): vol.All(
                        str, vol.Length(max=6)
                    )
                }
            ),
            errors=errors,
        )


class LgNetCastOptionsFlow(config_entries.OptionsFlow):
    """Implementation of the LG NetCast options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize NetCast option flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        # device: LgTVDevice = self.hass.data[DOMAIN][self.config_entry.entry_id]
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial options flow step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user",
        )
