"""Config flow for Ruckus Unleashed integration."""
from collections.abc import Mapping
from typing import Any

from aioruckus import AjaxSession, SystemStat
from aioruckus.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import (
    API_MESH_NAME,
    API_SYS_SYSINFO,
    API_SYS_SYSINFO_SERIAL,
    API_SYS_UNLEASHEDNETWORK,
    API_SYS_UNLEASHEDNETWORK_TOKEN,
    DOMAIN,
    KEY_SYS_SERIAL,
    KEY_SYS_TITLE,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    try:
        async with AjaxSession.async_create(
            data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD]
        ) as ruckus:
            system_info = await ruckus.api.get_system_info(
                SystemStat.SYSINFO,
                SystemStat.UNLEASHED_NETWORK,
            )
            mesh_name = (await ruckus.api.get_mesh_info())[API_MESH_NAME]
            zd_serial = (
                system_info[API_SYS_UNLEASHEDNETWORK][API_SYS_UNLEASHEDNETWORK_TOKEN]
                if API_SYS_UNLEASHEDNETWORK in system_info
                else system_info[API_SYS_SYSINFO][API_SYS_SYSINFO_SERIAL]
            )
            return {
                KEY_SYS_TITLE: mesh_name,
                KEY_SYS_SERIAL: zd_serial,
            }
    except AuthenticationError as autherr:
        raise InvalidAuth from autherr
    except (ConnectionRefusedError, ConnectionError, KeyError) as connerr:
        raise CannotConnect from connerr


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ruckus Unleashed."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(info[KEY_SYS_SERIAL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info[KEY_SYS_TITLE], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=DATA_SCHEMA,
            )
        return await self.async_step_user()


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
