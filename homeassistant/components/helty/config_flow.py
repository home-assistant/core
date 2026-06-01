"""Config flow for the Helty Flow integration."""

from typing import Any

from pyhelty import (
    DEFAULT_PORT,
    HeltyClient,
    HeltyConnectionError,
    HeltyError,
    HeltyResponseError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def _async_validate(data: dict[str, Any]) -> str:
    """Validate connectivity and return the device name (the stable unique id)."""
    client = HeltyClient(data[CONF_HOST], data[CONF_PORT])
    name = await client.async_get_name()
    if not name:
        raise HeltyResponseError("Device returned an empty name")
    return name


class HeltyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Helty Flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                name = await _async_validate(user_input)
            except HeltyConnectionError:
                errors["base"] = "cannot_connect"
            except HeltyError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(name)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration (e.g. the unit's IP address changed)."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            try:
                name = await _async_validate(user_input)
            except HeltyConnectionError:
                errors["base"] = "cannot_connect"
            except HeltyError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(name)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )
