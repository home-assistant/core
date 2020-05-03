"""Config flow for Met Office integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, MODE_3HOURLY, MODE_DAILY  # pylint: disable=unused-import
from .data import MetOfficeData

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate that the user input allows us to connect to DataPoint.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    api_key = data[CONF_API_KEY]
    latitude = data[CONF_LATITUDE]
    longitude = data[CONF_LONGITUDE]
    mode = data[CONF_MODE]

    metoffice_data = MetOfficeData(hass, api_key, latitude, longitude, mode)
    await metoffice_data.async_update_site()
    if metoffice_data.site_name is None:
        raise CannotConnect()

    return {"site_name": metoffice_data.site_name}


class MetOfficeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Met Office weather integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{DOMAIN}_{user_input[CONF_LATITUDE]}_{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                user_input[CONF_NAME] = info["site_name"]
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Required(CONF_MODE, default=MODE_3HOURLY,): vol.In(
                    [MODE_3HOURLY, MODE_DAILY]
                ),
            },
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Provide the handler for configuration option flow."""
        return MetOfficeOptionsFlowHandler(config_entry)


class MetOfficeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for the Met Office weather integration."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    def find_value_in_config_entry(self, key):
        """Find the configured key/value in the held config_entry."""
        if key in self.config_entry.options:
            return self.config_entry.options[key]
        return self.config_entry.data[key]

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title=None, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODE, default=self.find_value_in_config_entry(CONF_MODE),
                    ): vol.In([MODE_3HOURLY, MODE_DAILY]),
                },
                extra=vol.ALLOW_EXTRA,
            ),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
