"""Config flow for growatt server integration."""

from typing import Any

import growattServer
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import callback

from .const import (
    CONF_PLANT_ID,
    DEFAULT_URL,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
    SERVER_URLS,
)


class GrowattServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow class."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise growatt server flow."""
        self.api: growattServer.GrowattApi | None = None
        self.user_id = None
        self.data: dict[str, Any] = {}

    @callback
    def _async_show_user_form(self, errors=None):
        """Show the form to the user."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_URL, default=DEFAULT_URL): vol.In(SERVER_URLS),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self._async_show_user_form()

        # Initialise the library with the username & a random id each time it is started
        self.api = growattServer.GrowattApi(
            add_random_user_id=True, agent_identifier=user_input[CONF_USERNAME]
        )
        self.api.server_url = user_input[CONF_URL]
        login_response = await self.hass.async_add_executor_job(
            self.api.login, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        )

        if (
            not login_response["success"]
            and login_response["msg"] == LOGIN_INVALID_AUTH_CODE
        ):
            return self._async_show_user_form({"base": "invalid_auth"})
        self.user_id = login_response["user"]["id"]

        self.data = user_input
        return await self.async_step_plant()

    async def async_step_plant(self, user_input=None):
        """Handle adding a "plant" to Home Assistant."""
        plant_info = await self.hass.async_add_executor_job(
            self.api.plant_list, self.user_id
        )

        if not plant_info["data"]:
            return self.async_abort(reason="no_plants")

        plants = {plant["plantId"]: plant["plantName"] for plant in plant_info["data"]}

        if user_input is None and len(plant_info["data"]) > 1:
            data_schema = vol.Schema({vol.Required(CONF_PLANT_ID): vol.In(plants)})

            return self.async_show_form(step_id="plant", data_schema=data_schema)

        if user_input is None and len(plant_info["data"]) == 1:
            user_input = {CONF_PLANT_ID: plant_info["data"][0]["plantId"]}

        user_input[CONF_NAME] = plants[user_input[CONF_PLANT_ID]]
        await self.async_set_unique_id(user_input[CONF_PLANT_ID])
        self._abort_if_unique_id_configured()
        self.data.update(user_input)
        return self.async_create_entry(title=self.data[CONF_NAME], data=self.data)
