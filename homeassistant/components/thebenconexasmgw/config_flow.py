"""Config flow for the Theben Conexa Smartmeter gateway integration."""

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .smgw import ConexaSMGW, checkNetworkConnection

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOST, description={"suggested_value": "192.168.1.200"}
        ): str,  # TODO many electricity grid operators use this IP as 'hardcoded' static IP should this integration assume so also? pylint: disable=fixme
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    try:
        # This function tries to establish a TCP connection and raises an exception on error
        await checkNetworkConnection(data[CONF_HOST])
    except (OSError, aiohttp.ClientError) as e:
        raise CannotConnect from e

    try:
        m2murl = await ConexaSMGW.buildCompleteUrl(
            async_get_clientsession(hass),
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        _LOGGER.debug("SMGW returned valid query URL %s", m2murl)
    except (OSError, aiohttp.ClientError) as e:
        # The smgw unfortunately does not reply with invalid auth it just times out
        # So after we checked that connection is possible we assume Invalid auth if something happens
        raise InvalidAuth from e

    return {"title": "Smartmeter Gateway", "m2mUrl": m2murl}


class ThebenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Theben Conexa Smartmeter gateway."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                }
            )
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
                user_input["m2mUrl"] = info["m2mUrl"]
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
