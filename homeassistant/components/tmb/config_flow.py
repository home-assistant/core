"""Config flow for TMB."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import (
    CONF_FROM_LATITUDE,
    CONF_FROM_LONGITUDE,
    CONF_LINE,
    CONF_SERVICE,
    CONF_STOP,
    CONF_TO_LATITUDE,
    CONF_TO_LONGITUDE,
    DOMAIN,
    SERVICE_IBUS,
    SERVICE_PLANNER,
)


class TMBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """TMB config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # Check if user has configured the tmb object on the YAML file
        if DOMAIN not in self.hass.data:
            return self.async_abort(reason="missing_configuration")

        return await self.async_step_select()

    async def async_step_select(self, user_input=None):
        """Handle which service do the user wants to use for the sensor."""
        if user_input is not None:
            if user_input[CONF_SERVICE] == SERVICE_IBUS:
                return await self.async_step_ibus()
            return await self.async_step_planner()

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {vol.Required(CONF_SERVICE): vol.In([SERVICE_IBUS, SERVICE_PLANNER])}
            ),
        )

    async def async_step_ibus(self, user_input=None):
        """Handle input for iBus service configuration."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=f"{SERVICE_IBUS}: {user_input[CONF_NAME]}",
                data={
                    CONF_SERVICE: SERVICE_IBUS,
                    CONF_LINE: user_input[CONF_LINE],
                    CONF_STOP: user_input[CONF_STOP],
                    CONF_NAME: user_input[CONF_NAME],
                },
            )

        # Specify items in the order they are to be displayed in the UI
        data_schema = {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_LINE): str,
            vol.Required(CONF_STOP): str,
        }

        return self.async_show_form(
            step_id="ibus", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_planner(self, user_input=None):
        """Handle input for Planner service configuration."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=f"{SERVICE_PLANNER}: {user_input[CONF_NAME]}",
                data={
                    CONF_SERVICE: SERVICE_PLANNER,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_FROM_LATITUDE: user_input[CONF_FROM_LATITUDE],
                    CONF_FROM_LONGITUDE: user_input[CONF_FROM_LONGITUDE],
                    CONF_TO_LATITUDE: user_input[CONF_TO_LATITUDE],
                    CONF_TO_LONGITUDE: user_input[CONF_TO_LONGITUDE],
                },
            )

        data_schema = {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_FROM_LATITUDE): str,
            vol.Required(CONF_FROM_LONGITUDE): str,
            vol.Required(CONF_TO_LATITUDE): str,
            vol.Required(CONF_TO_LONGITUDE): str,
        }

        return self.async_show_form(
            step_id="planner", data_schema=vol.Schema(data_schema), errors=errors
        )
