"""Config flow for Vilfo Router integration."""
import ipaddress
import logging
import re

from vilfo import Client as VilfoClient
from vilfo.exceptions import (
    AuthenticationException as VilfoAuthenticationException,
    VilfoException,
)
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_ID, CONF_MAC

from .const import ATTR_DEFAULT_HOST, DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=ATTR_DEFAULT_HOST): str,
        vol.Required(CONF_ACCESS_TOKEN, default=""): str,
    }
)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version == (4 or 6):
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    # Validate the host before doing anything else.
    if not host_valid(data[CONF_HOST]):
        raise InvalidHost

    config = {}

    # Attempt to connect and call the ping endpoint.
    # This doesn't validate authentication.
    controller = VilfoClient(host=data[CONF_HOST], token=data[CONF_ACCESS_TOKEN])
    try:
        controller.ping()
    except VilfoException:
        raise CannotConnect

    # Perform a call that requires authentication.
    try:
        controller.get_board_information()
    except VilfoAuthenticationException:
        raise InvalidAuth

    # Return some info we want to store in the config entry.
    config["title"] = f"{data[CONF_HOST]}"
    config[CONF_MAC] = controller.mac
    config[CONF_HOST] = data[CONF_HOST]

    if controller.mac:
        config[CONF_ID] = controller.mac
    else:
        config[CONF_ID] = data[CONF_HOST]

    return config


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vilfo Router."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(info[CONF_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidHost:
                errors[CONF_HOST] = "wrong_host"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate that a configuration already has been set up for the host."""
