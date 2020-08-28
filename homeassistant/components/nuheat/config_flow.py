"""Config flow for NuHeat integration."""
import logging

import nuheat
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    HTTP_BAD_REQUEST,
    HTTP_INTERNAL_SERVER_ERROR,
)

from .const import CONF_SERIAL_NUMBER
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SERIAL_NUMBER): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    api = nuheat.NuHeat(data[CONF_USERNAME], data[CONF_PASSWORD])

    try:
        await hass.async_add_executor_job(api.authenticate)
    except requests.exceptions.Timeout as ex:
        raise CannotConnect from ex
    except requests.exceptions.HTTPError as ex:
        if (
            ex.response.status_code > HTTP_BAD_REQUEST
            and ex.response.status_code < HTTP_INTERNAL_SERVER_ERROR
        ):
            raise InvalidAuth from ex
        raise CannotConnect from ex
    #
    # The underlying module throws a generic exception on login failure
    #
    except Exception as ex:  # pylint: disable=broad-except
        raise InvalidAuth from ex

    try:
        thermostat = await hass.async_add_executor_job(
            api.get_thermostat, data[CONF_SERIAL_NUMBER]
        )
    except requests.exceptions.HTTPError as ex:
        raise InvalidThermostat from ex

    return {"title": thermostat.room, "serial_number": thermostat.serial_number}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NuHeat."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidThermostat:
                errors["base"] = "invalid_thermostat"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(info["serial_number"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        await self.async_set_unique_id(user_input[CONF_SERIAL_NUMBER])
        self._abort_if_unique_id_configured()

        return await self.async_step_user(user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidThermostat(exceptions.HomeAssistantError):
    """Error to indicate there is invalid thermostat."""
