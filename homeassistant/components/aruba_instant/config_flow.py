"""Config flow for Aruba Instant integration."""
import logging

import voluptuous as vol
from instantpy import InstantVC

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_PORT,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL
)  # pylint:disable=unused-import

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_VERIFY_SSL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


async def async_validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    instant_validate = InstantVC(data.get('host'), data.get('username'), data.get('password'), port=data.get('port'), ssl_verify=data.get('verify_ssl'))

    connection = await hass.async_add_executor_job(
        instant_validate.login
    )
    if connection is True:
        if instant_validate.logged_in is False:
            raise InvalidAuth
    elif "[SSL: CERTIFICATE_VERIFY_FAILED]" in connection.args[0].args[0]:
        raise CannotVerifySSLCert
    else:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": "Aruba Instant VC"}

@config_entries.HANDLERS.register(DOMAIN)
class InstantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aruba Instant."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                self.config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_PORT: user_input.get(CONF_PORT),
                    CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL)
                }
                await self.async_set_unique_id(user_input[CONF_HOST])
                info = await async_validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotVerifySSLCert:
                errors["base"] = "cannot_verify_ssl_cert"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


# class InstantOptionsFlowHandler(config_entries.OptionsFlow):
#     """Handle Aruba Instant options."""

#     def __init__(self, config_entry):
#         """Initialize Aruba Instant options flow."""
#         self.config_entry = config_entry

#     async def async_step_init(self, user_input=None):
#         """Manage the options."""

#         client_cache = {}
#         for client in self.hass.data[DOMAIN][self.config_entry.entry_id][
#             "client_cache"
#         ].keys():
#             client_cache.update(
#                 {
#                     client: self.hass.data[DOMAIN][self.config_entry.entry_id][
#                         "client_cache"
#                     ][client]["name"]
#                 }
#             )

#         OPTIONS_DATA_SCHEMA = vol.Schema(
#             {vol.Required("Clients", description="Clients"): vol.In(client_cache)}
#         )

#         if user_input is not None:
#             return self.async_create_entry(
#                 title="Configure your options!", data=user_input
#             )

#         return self.async_show_form(step_id="init", data_schema=OPTIONS_DATA_SCHEMA,)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotVerifySSLCert(exceptions.HomeAssistantError):
    """Error to indicate an issue validating an SSL certificate."""
