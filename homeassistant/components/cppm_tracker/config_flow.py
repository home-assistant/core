"""Config flow for the Aruba ClearPass (cppm_tracker) integration."""

import json
from typing import Any, override

from clearpasspy import ClearPass
import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_ID, CONF_HOST

from .const import DOMAIN, GRANT_TYPE

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_API_KEY): str,
    }
)


def validate_connection(data: dict[str, Any]) -> None:
    """Validate that we can authenticate against ClearPass."""
    credentials = {
        "server": data[CONF_HOST],
        "grant_type": GRANT_TYPE,
        "secret": data[CONF_API_KEY],
        "client": data[CONF_CLIENT_ID],
    }
    try:
        cppm = ClearPass(credentials)
    except KeyError as err:
        # clearpasspy reads the access token straight out of the response, so
        # rejected credentials surface as a missing key.
        raise InvalidAuth from err
    except (requests.exceptions.RequestException, json.JSONDecodeError) as err:
        raise CannotConnect from err
    if cppm.access_token is None:
        raise InvalidAuth


class CppmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aruba ClearPass."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await self.hass.async_add_executor_job(validate_connection, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a configuration from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})

        try:
            await self.hass.async_add_executor_job(validate_connection, import_data)
        except CannotConnect, InvalidAuth:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title=import_data[CONF_HOST], data=import_data)


class CannotConnect(Exception):
    """Error to indicate we cannot connect to ClearPass."""


class InvalidAuth(Exception):
    """Error to indicate the credentials are invalid."""
