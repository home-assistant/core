"""Config flow for Sun WEG integration."""
from sunweg.api import APIHelper
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_PLANT_ID, DOMAIN


class SunWEGConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow class."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise sun weg server flow."""
        self.api: APIHelper = None
        self.data: dict = {}

    @callback
    def _async_show_user_form(self, errors=None) -> FlowResult:
        """Show the form to the user."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self._async_show_user_form()

        # Initialise the library with the username & password
        self.api = APIHelper(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        login_response = await self.hass.async_add_executor_job(self.api.authenticate)

        if not login_response:
            return self._async_show_user_form({"base": "invalid_auth"})

        # Store authentication info
        self.data = user_input
        return await self.async_step_plant()

    async def async_step_plant(self, user_input=None) -> FlowResult:
        """Handle adding a "plant" to Home Assistant."""
        plant_list = await self.hass.async_add_executor_job(self.api.listPlants)

        if len(plant_list) == 0:
            return self.async_abort(reason="no_plants")

        plants = {plant.id: plant.name for plant in plant_list}

        if user_input is None and len(plant_list) > 1:
            data_schema = vol.Schema({vol.Required(CONF_PLANT_ID): vol.In(plants)})

            return self.async_show_form(step_id="plant", data_schema=data_schema)

        if user_input is None and len(plant_list) == 1:
            user_input = {CONF_PLANT_ID: plant_list[0].id}

        user_input[CONF_NAME] = plants[user_input[CONF_PLANT_ID]]
        await self.async_set_unique_id(user_input[CONF_PLANT_ID])
        self._abort_if_unique_id_configured()
        self.data.update(user_input)
        return self.async_create_entry(title=self.data[CONF_NAME], data=self.data)
