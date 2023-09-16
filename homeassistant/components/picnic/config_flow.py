"""Config flow for Picnic integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from python_picnic_api import PicnicAPI
from python_picnic_api.session import PicnicAuthError
import requests
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform the re-auth step upon an API authentication error."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle the authentication step, this is the generic step for both `step_user` and `step_reauth`."""
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
            data = {
                CONF_ACCESS_TOKEN: auth_token,
                CONF_COUNTRY_CODE: user_input[CONF_COUNTRY_CODE],
            }
            existing_entry = await self.async_set_unique_id(info["unique_id"])

            # Abort if we're adding a new config and the unique id is already in use, else create the entry
            if self.source != SOURCE_REAUTH:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=data)

            # In case of re-auth, only continue if an exiting account exists with the same unique id
            if existing_entry:
                self.hass.config_entries.async_update_entry(existing_entry, data=data)
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            # Set the error because the account is different
            errors["base"] = "different_account"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
