"""Config flow for Picnic integration."""
import logging

import requests
import voluptuous as vol
from python_picnic_api import PicnicAPI

from homeassistant import config_entries, core, exceptions
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_COUNTRY_CODE, \
    COUNTRY_CODES  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Required(CONF_COUNTRY_CODE, default=COUNTRY_CODES[0]): vol.In(
        COUNTRY_CODES
    )
})


class PicnicHub:
    """Hub class to test user authentication."""

    def authenticate(self, username, password, country_code) -> None:
        """Test if we can authenticate with the Picnic API."""
        picnic = PicnicAPI(username, password, country_code)
        return picnic.get_user()


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = PicnicHub()

    try:
        user_data = await hass.async_add_executor_job(
            hub.authenticate, data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_COUNTRY_CODE]
        )
    except requests.exceptions.ConnectionError:
        raise CannotConnect
    except Exception:  # pylint: disable=broad-except
        raise InvalidAuth

    # Return the validation result
    return {
        "title": user_data["address"]["street"] + " " +
            str(user_data["address"]["house_number"]) +
            user_data["address"]["house_number_ext"],
        "unique_id": user_data["user_id"]
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
            info = await validate_input(self.hass, user_input)
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

            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
