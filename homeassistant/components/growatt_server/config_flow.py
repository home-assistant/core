"""Config flow for growatt server integration."""
import voluptuous as vol

import growattServer

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD
from .const import DOMAIN, CONF_PLANT_ID, DEFAULT_NAME


class GrowattServerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow class."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialise growatt server flow."""
        self.user_input = {}
        self.api = growattServer.GrowattApi()

    async def async_step_plant(self, user_input=None):
        """Handle a flow initialized by the user."""
        user_input = {**self.user_input, **user_input}

        if CONF_PLANT_ID not in user_input:
            login_response = self.api.login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            user_id = login_response["userId"]
            plant_info = self.api.plant_list(user_id)

            if len(plant_info["data"]) == 0:
                return await self._show_user_form({"base": "no_plants"})
            if len(plant_info["data"]) > 1:
                plants = {}
                for plant in plant_info["data"]:
                    plants[plant["plantId"]] = plant["plantName"]
                self.user_input = user_input
                return await self._show_plant_id_form(None, plants)
            user_input[CONF_PLANT_ID] = plant_info["data"][0]["plantId"]

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

    async def _show_user_form(self, errors=None):
        """Show the form to the user."""
        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def _show_plant_id_form(self, errors=None, plants=None):
        """Show the form to the user."""
        data_schema = vol.Schema({vol.Required(CONF_PLANT_ID): vol.In(plants or {})})

        return self.async_show_form(
            step_id="plant", data_schema=data_schema, errors=errors
        )

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_user_form()

        login_response = self.api.login(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        )

        if not login_response["success"] and login_response["errCode"] == "102":
            return await self._show_user_form({"base": "auth_error"})

        return await self.async_step_plant(user_input)
