"""Config flow for growatt server integration"""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD
from .const import DOMAIN, CONF_PLANT_ID, DEFAULT_NAME


@config_entries.HANDLERS.register(DOMAIN)
class GrowattServerConfigFlow(config_entries.ConfigFlow):
    """Config flow class"""
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_init(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_user(user_input)

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(CONF_PLANT_ID): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        import growattServer

        api = growattServer.GrowattApi()
        login_response = api.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

        if not login_response["success"] and login_response["errCode"] == "102":
            return await self._show_form({"base": "auth_error"})
        user_id = login_response["userId"]

        if CONF_PLANT_ID not in user_input:
            plant_info = api.plant_list(user_id)
            if len(plant_info["data"]) > 1:
                return await self._show_form({CONF_PLANT_ID: "multiple_plants"})
            user_input[CONF_PLANT_ID] = plant_info["data"][0]["plantId"]

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
