from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_MIN_TEMPERATURE,
    CONF_MAX_TEMPERATURE,
    CONF_MIN_MOISTURE,
    CONF_MAX_MOISTURE,
    CONF_MIN_CONDUCTIVITY,
    CONF_MAX_CONDUCTIVITY,
    CONF_MIN_BRIGHTNESS,
    CONF_MAX_BRIGHTNESS,
    CONF_MIN_BATTERY_LEVEL,
)

@config_entries.HANDLERS.register(DOMAIN)
class PlantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Plant integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Process the user input here
            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("moisture"): str,
                vol.Optional("battery"): str,
                vol.Optional("temperature"): str,
                vol.Optional("conductivity"): str,
                vol.Optional("brightness"): str,
                vol.Optional(CONF_MIN_TEMPERATURE, default=15): int,
                vol.Optional(CONF_MAX_TEMPERATURE, default=35): int,
                vol.Optional(CONF_MIN_MOISTURE, default=20): int,
                vol.Optional(CONF_MAX_MOISTURE, default=60): int,
                vol.Optional(CONF_MIN_CONDUCTIVITY, default=350): int,
                vol.Optional(CONF_MAX_CONDUCTIVITY, default=2000): int,
                vol.Optional(CONF_MIN_BRIGHTNESS, default=1000): int,
                vol.Optional(CONF_MAX_BRIGHTNESS, default=10000): int,
                vol.Optional(CONF_MIN_BATTERY_LEVEL, default=10): int,
            }),
            errors=errors,
        )

    @callback
    def async_get_options_flow(self, config_entry):
        return PlantOptionsFlowHandler(config_entry)

class PlantOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the Plant integration."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("min_temperature", default=self.config_entry.options.get("min_temperature", 15)): int,
                vol.Optional("max_temperature", default=self.config_entry.options.get("max_temperature", 35)): int,
                vol.Optional("min_moisture", default=self.config_entry.options.get("min_moisture", 20)): int,
                vol.Optional("max_moisture", default=self.config_entry.options.get("max_moisture", 60)): int,
                vol.Optional("min_conductivity", default=self.config_entry.options.get("min_conductivity", 350)): int,
                vol.Optional("max_conductivity", default=self.config_entry.options.get("max_conductivity", 2000)): int,
                vol.Optional("min_brightness", default=self.config_entry.options.get("min_brightness", 1000)): int,
                vol.Optional("max_brightness", default=self.config_entry.options.get("max_brightness", 10000)): int,
                vol.Optional("min_battery", default=self.config_entry.options.get("min_battery", 10)): int,
            }),
        )
