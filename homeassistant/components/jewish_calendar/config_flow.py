"""Config flow for Jewish calendar integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DIASPORA,
    CONF_LANGUAGE,
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_CANDLE_LIGHT,
    DEFAULT_DIASPORA,
    DEFAULT_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class JewishCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jewish calendar."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return JewishCalendarOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:

            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Optional(CONF_DIASPORA, default=DEFAULT_DIASPORA): bool,
                    vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(
                        ["hebrew", "english"]
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning("Only one configuration of Jewish calendar is allowed")
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user(import_config)


class JewishCalendarOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Jewish Calendar options."""

    def __init__(self, config_entry):
        """Initialize Jewidh Calendar options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Jewish Calendar options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_CANDLE_LIGHT_MINUTES,
                default=self.config_entry.options.get(
                    CONF_CANDLE_LIGHT_MINUTES, DEFAULT_CANDLE_LIGHT
                ),
            ): int,
            # Default of 0 means use 8.5 degrees / 'three_stars' time.
            vol.Optional(
                CONF_HAVDALAH_OFFSET_MINUTES,
                default=self.config_entry.options.get(
                    CONF_HAVDALAH_OFFSET_MINUTES, DEFAULT_HAVDALAH_OFFSET_MINUTES
                ),
            ): int,
            vol.Optional(
                CONF_LATITUDE,
                default=self.config_entry.options.get(
                    CONF_LATITUDE, self.hass.config.latitude
                ),
            ): cv.latitude,
            vol.Optional(
                CONF_LONGITUDE,
                default=self.config_entry.options.get(
                    CONF_LONGITUDE, self.hass.config.longitude
                ),
            ): cv.longitude,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
