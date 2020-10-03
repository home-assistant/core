"""Config flow to configure demo component."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

# pylint: disable=unused-import
from . import DOMAIN

CONF_STRING = "string"
CONF_BOOLEAN = "bool"
CONF_INT = "int"
CONF_SELECT = "select"
CONF_MULTISELECT = "multi"


class DemoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Demo configuration flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        return self.async_create_entry(title="Demo", data={})


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_options_1()

    async def async_step_options_1(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_options_2()

        return self.async_show_form(
            step_id="options_1",
            data_schema=vol.Schema(
                {
                    vol.Required("constant"): "Constant Value",
                    vol.Optional(
                        CONF_BOOLEAN,
                        default=self.config_entry.options.get(CONF_BOOLEAN, False),
                    ): bool,
                    vol.Optional(
                        CONF_INT,
                        default=self.config_entry.options.get(CONF_INT, 10),
                    ): int,
                }
            ),
        )

    async def async_step_options_2(self, user_input=None):
        """Manage the options 2."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="options_2",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_STRING,
                        default=self.config_entry.options.get(
                            CONF_STRING,
                            "Default",
                        ),
                    ): str,
                    vol.Optional(
                        CONF_SELECT,
                        default=self.config_entry.options.get(CONF_SELECT, "default"),
                    ): vol.In(["default", "other"]),
                    vol.Optional(
                        CONF_MULTISELECT,
                        default=self.config_entry.options.get(
                            CONF_MULTISELECT, ["default"]
                        ),
                    ): cv.multi_select({"default": "Default", "other": "Other"}),
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(title="", data=self.options)
