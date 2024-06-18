"""Config flow for Vilfo Router integration."""

import logging

from vilfo import Client as VilfoClient
from vilfo.exceptions import (
    AuthenticationException as VilfoAuthenticationException,
    VilfoException,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_ID, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.network import is_host_valid

from .const import DOMAIN, ROUTER_DEFAULT_HOST

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=ROUTER_DEFAULT_HOST): str,
        vol.Required(CONF_ACCESS_TOKEN, default=""): str,
    }
)

RESULT_SUCCESS = "success"
RESULT_CANNOT_CONNECT = "cannot_connect"
RESULT_INVALID_AUTH = "invalid_auth"


def _try_connect_and_fetch_basic_info(host, token):
    """Attempt to connect and call the ping endpoint and, if successful, fetch basic information."""

    # Perform the ping. This doesn't validate authentication.
    controller = VilfoClient(host=host, token=token)
    result = {"type": None, "data": {}}

    try:
        controller.ping()
    except VilfoException:
        result["type"] = RESULT_CANNOT_CONNECT
        result["data"] = CannotConnect
        return result

    # Perform a call that requires authentication.
    try:
        controller.get_board_information()
    except VilfoAuthenticationException:
        result["type"] = RESULT_INVALID_AUTH
        result["data"] = InvalidAuth
        return result

    if controller.mac:
        result["data"][CONF_ID] = controller.mac
        result["data"][CONF_MAC] = controller.mac
    else:
        result["data"][CONF_ID] = host
        result["data"][CONF_MAC] = None

    result["type"] = RESULT_SUCCESS

    return result


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    # Validate the host before doing anything else.
    if not is_host_valid(data[CONF_HOST]):
        raise InvalidHost

    config = {}

    result = await hass.async_add_executor_job(
        _try_connect_and_fetch_basic_info, data[CONF_HOST], data[CONF_ACCESS_TOKEN]
    )

    if result["type"] != RESULT_SUCCESS:
        raise result["data"]

    # Return some info we want to store in the config entry.
    result_data = result["data"]
    config["title"] = f"{data[CONF_HOST]}"
    config[CONF_MAC] = result_data[CONF_MAC]
    config[CONF_HOST] = data[CONF_HOST]
    config[CONF_ID] = result_data[CONF_ID]

    return config


class DomainConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vilfo Router."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidHost:
                errors[CONF_HOST] = "wrong_host"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Unexpected exception: %s", err)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info[CONF_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidHost(HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""
