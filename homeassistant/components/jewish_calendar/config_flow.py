"""Config flow for Jewish calendar integration."""
import logging

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from .const import (
    DEFAULT_NAME,
    CONF_DIASPORA,
    CONF_LANGUAGE,
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DOMAIN,
    DATA_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jewish calendar."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={
                        CONF_DIASPORA: user_input[CONF_DIASPORA],
                        CONF_LANGUAGE: user_input[CONF_LANGUAGE],
                        CONF_CANDLE_LIGHT_MINUTES: user_input[
                            CONF_CANDLE_LIGHT_MINUTES
                        ],
                        CONF_HAVDALAH_OFFSET_MINUTES: user_input[
                            CONF_HAVDALAH_OFFSET_MINUTES
                        ],
                        CONF_LATITUDE: user_input.get(
                            CONF_LATITUDE, self.hass.config.latitude
                        ),
                        CONF_LONGITUDE: user_input.get(
                            CONF_LONGITUDE, self.hass.config.longitude
                        ),
                    },
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
