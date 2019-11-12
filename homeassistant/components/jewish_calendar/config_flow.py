"""Config flow for Jewish calendar integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

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
    DATA_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)


class JewishCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jewish calendar."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={
                    CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                    CONF_DIASPORA: user_input.get(CONF_DIASPORA, DEFAULT_DIASPORA),
                    CONF_LANGUAGE: user_input.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                    CONF_CANDLE_LIGHT_MINUTES: user_input.get(
                        CONF_CANDLE_LIGHT_MINUTES, DEFAULT_CANDLE_LIGHT
                    ),
                    CONF_HAVDALAH_OFFSET_MINUTES: user_input.get(
                        CONF_HAVDALAH_OFFSET_MINUTES, DEFAULT_HAVDALAH_OFFSET_MINUTES
                    ),
                    CONF_LATITUDE: user_input.get(
                        CONF_LATITUDE, self.hass.config.latitude
                    ),
                    CONF_LONGITUDE: user_input.get(
                        CONF_LONGITUDE, self.hass.config.longitude
                    ),
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA), errors={}
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning("Only one configuration of Jewish calendar is allowed")
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user(import_config)
