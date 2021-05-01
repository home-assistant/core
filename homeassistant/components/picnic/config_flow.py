"""Config flow for Picnic integration."""
from __future__ import annotations

import logging

from python_picnic_api import PicnicAPI
from python_picnic_api.session import PicnicAuthError
import requests
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME

from .const import CONF_COUNTRY_CODE, COUNTRY_CODES, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_COUNTRY_CODE, default=COUNTRY_CODES[0]): vol.In(
            COUNTRY_CODES
        ),
    }
)


class PicnicHub:
    """Hub class to test user authentication."""

    @staticmethod
    def authenticate(username, password, country_code) -> tuple[str, dict]:
        """Test if we can authenticate with the Picnic API."""
        picnic = PicnicAPI(username, password, country_code)
        return picnic.session.auth_token, picnic.get_user()


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = PicnicHub()

    try:
        auth_token, user_data = await hass.async_add_executor_job(
            hub.authenticate,
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data[CONF_COUNTRY_CODE],
        )
    except requests.exceptions.ConnectionError as error:
        raise CannotConnect from error
    except PicnicAuthError as error:
        raise InvalidAuth from error

    # Return the validation result
    address = (
        f'{user_data["address"]["street"]} {user_data["address"]["house_number"]}'
        + f'{user_data["address"]["house_number_ext"]}'
    )
    return auth_token, {
        "title": address,
        "unique_id": user_data["user_id"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Picnic."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            auth_token, info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Set the unique id and abort if it already exists
            await self.async_set_unique_id(info["unique_id"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=info["title"],
                data={
                    CONF_ACCESS_TOKEN: auth_token,
                    CONF_COUNTRY_CODE: user_input[CONF_COUNTRY_CODE],
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
