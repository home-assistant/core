"""Config flow for flo integration."""

from typing import Any, override

from aioflo.errors import RequestError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import async_get_flo_api
from .const import CONF_USE_SSO, DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(hass: HomeAssistant, data) -> bool:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    Returns True if Moen SSO was used.
    """

    try:
        _api, used_sso = await async_get_flo_api(
            hass, data[CONF_USERNAME], data[CONF_PASSWORD]
        )
    except RequestError as request_error:
        LOGGER.error("Error connecting to the Flo API: %s", request_error)
        raise CannotConnect from request_error
    return used_sso


class FloConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for flo."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            try:
                used_sso = await validate_input(self.hass, user_input)
                entry_data = dict(user_input)
                if used_sso:
                    entry_data[CONF_USE_SSO] = True
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=entry_data
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
