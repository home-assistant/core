"""Config flow for OpenPlantBook integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core

from . import CannotConnect, InvalidAuth, OpenPlantBookApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
DATA_SCHEMA = vol.Schema({"client_id": str, "secret": str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    api = OpenPlantBookApi(hass)
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    try:
        token = await api.get_plantbook_token(data["client_id"], data["secret"])
        if not token:
            raise CannotConnect
    except CannotConnect:
        _LOGGER.error("Unable to connect to the OpenPlantbook API")
        raise CannotConnect
        return False
    except InvalidAuth:
        _LOGGER.error("Authentication failed when connecting to the OpenPlantbook API")
        raise InvalidAuth
        return False
    except Exception as e:
        _LOGGER.error(
            "Unknown error «%s» when connecting the OpenPlantbook API", str(e)
        )
        raise CannotConnect
        return False

    return {"title": "Openplantbook API", "token": token}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenPlantBook."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                if info:
                    user_input["token"] = info["token"]
                    return self.async_create_entry(title=info["title"], data=user_input)
                else:
                    raise CannotConnect
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
