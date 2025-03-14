"""Config flow for Ruckus integration."""

from collections.abc import Mapping
import logging
from typing import Any

from aioruckus import AjaxSession, SystemStat
from aioruckus.exceptions import AuthenticationError, SchemaError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    API_MESH_NAME,
    API_SYS_SYSINFO,
    API_SYS_SYSINFO_SERIAL,
    DOMAIN,
    KEY_SYS_SERIAL,
    KEY_SYS_TITLE,
)

_LOGGER = logging.getLogger(__package__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    try:
        async with AjaxSession.async_create(
            data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD]
        ) as ruckus:
            mesh_info = await ruckus.api.get_mesh_info()
            system_info = await ruckus.api.get_system_info(SystemStat.SYSINFO)
    except AuthenticationError as autherr:
        raise InvalidAuth from autherr
    except (ConnectionError, SchemaError) as connerr:
        raise CannotConnect from connerr

    mesh_name = mesh_info[API_MESH_NAME]
    zd_serial = system_info[API_SYS_SYSINFO][API_SYS_SYSINFO_SERIAL]

    return {
        KEY_SYS_TITLE: mesh_name,
        KEY_SYS_SERIAL: zd_serial,
    }


class RuckusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ruckus."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info[KEY_SYS_SERIAL])
                if self.source != SOURCE_REAUTH:
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=info[KEY_SYS_TITLE], data=user_input
                    )
                reauth_entry = self._get_reauth_entry()
                if info[KEY_SYS_SERIAL] == reauth_entry.unique_id:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data=user_input
                    )
                errors["base"] = "invalid_host"

        data_schema = DATA_SCHEMA
        if self.source == SOURCE_REAUTH:
            data_schema = self.add_suggested_values_to_schema(
                data_schema, self._get_reauth_entry().data
            )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_user()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
