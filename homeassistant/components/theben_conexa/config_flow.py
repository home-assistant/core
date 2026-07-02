"""Config flow for the Theben Conexa Smartmeter gateway integration."""

import logging
from typing import Any, override

import aiohttp
from theben_conexa_smgw import ConexaSMGW, checkNetworkConnection
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, description={"suggested_value": "192.168.1.200"}): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ThebenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Theben Conexa Smartmeter gateway."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                try:
                    # This function tries to establish a TCP connection and raises an exception on error
                    await checkNetworkConnection(user_input[CONF_HOST])
                except (OSError, aiohttp.ClientError) as e:
                    raise CannotConnect from e

                try:
                    local_api = await ConexaSMGW.create(
                        async_get_clientsession(self.hass),
                        user_input[CONF_HOST],
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                    )
                    await self.async_set_unique_id(
                        f"{local_api.gatewayInfo.smgwID}-{user_input[CONF_USERNAME]}"
                    )
                    self._abort_if_unique_id_configured()
                except (OSError, aiohttp.ClientError) as e:
                    # The smgw unfortunately does not reply with invalid auth it just times out
                    # So after we checked that connection is possible we assume Invalid auth if something happens
                    raise InvalidAuth from e

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except AbortFlow:
                raise  # error str is already set by _abort_if_unique_id_configured
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Smartmeter Gateway", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
