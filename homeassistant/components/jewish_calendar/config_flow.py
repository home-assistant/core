"""Config flow for Jewish calendar integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_TIME_ZONE,
)
from homeassistant.core import callback
from homeassistant import exceptions
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

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_DIASPORA, default=DEFAULT_DIASPORA): bool,
        vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(
            ["hebrew", "english"]
        ),
        # Default is empty, unless user wants to override
        vol.Optional(CONF_LATITUDE): float,
        vol.Optional(CONF_LONGITUDE): float,
        vol.Optional(CONF_ELEVATION): float,
        vol.Optional(CONF_TIME_ZONE): str,
    }
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass, data):
    """Validate the user input."""
    return {"title": data[CONF_NAME]}


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
                if all(
                    _value == entry.as_dict().get(_key)
                    for _key, _value in user_input.items()
                    if _key != CONF_NAME
                ):
                    return self.async_abort(reason="already_configured")

                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)


class JewishCalendarOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Jewish Calendar options."""

    def __init__(self, config_entry):
        """Initialize Jewish Calendar options flow."""
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
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
