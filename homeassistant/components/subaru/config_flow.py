"""Config flow for Subaru integration."""
from datetime import datetime
import logging

from subarulink import (
    Controller as SubaruAPI,
    InvalidCredentials,
    InvalidPIN,
    SubaruException,
)
from subarulink.const import COUNTRY_CAN, COUNTRY_USA
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_PIN, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import CONF_COUNTRY, CONF_UPDATE_ENABLED, DOMAIN

_LOGGER = logging.getLogger(__name__)
PIN_SCHEMA = vol.Schema({vol.Required(CONF_PIN): str})


class SubaruConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Subaru."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize config flow."""
        self.config_data = {CONF_PIN: None}
        self.controller = None

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        error = None

        if user_input:
            if user_input[CONF_USERNAME] in [
                entry.data[CONF_USERNAME] for entry in self._async_current_entries()
            ]:
                return self.async_abort(reason="already_configured")

            try:
                await self.validate_login_creds(user_input)
            except InvalidCredentials:
                error = {"base": "invalid_auth"}
            except SubaruException as ex:
                _LOGGER.error("Unable to communicate with Subaru API: %s", ex.message)
                return self.async_abort(reason="cannot_connect")
            else:
                if self.controller.is_pin_required():
                    return await self.async_step_pin()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=self.config_data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=user_input.get(CONF_USERNAME) if user_input else "",
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=user_input.get(CONF_PASSWORD) if user_input else "",
                    ): str,
                    vol.Required(
                        CONF_COUNTRY,
                        default=user_input.get(CONF_COUNTRY)
                        if user_input
                        else COUNTRY_USA,
                    ): vol.In([COUNTRY_CAN, COUNTRY_USA]),
                }
            ),
            errors=error,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def validate_login_creds(self, data):
        """Validate the user input allows us to connect.

        data: contains values provided by the user.
        """
        websession = aiohttp_client.async_get_clientsession(self.hass)
        now = datetime.now()
        if not data.get(CONF_DEVICE_ID):
            data[CONF_DEVICE_ID] = int(now.timestamp())
        date = now.strftime("%Y-%m-%d")
        device_name = "Home Assistant: Added " + date

        self.controller = SubaruAPI(
            websession,
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            device_id=data[CONF_DEVICE_ID],
            pin=None,
            device_name=device_name,
            country=data[CONF_COUNTRY],
        )
        _LOGGER.debug(
            "Setting up first time connection to Subaru API.  This may take up to 20 seconds"
        )
        if await self.controller.connect():
            _LOGGER.debug("Successfully authenticated and authorized with Subaru API")
            self.config_data.update(data)

    async def async_step_pin(self, user_input=None):
        """Handle second part of config flow, if required."""
        error = None
        if user_input and self.controller.update_saved_pin(user_input[CONF_PIN]):
            try:
                vol.Match(r"[0-9]{4}")(user_input[CONF_PIN])
                await self.controller.test_pin()
            except vol.Invalid:
                error = {"base": "bad_pin_format"}
            except InvalidPIN:
                error = {"base": "incorrect_pin"}
            else:
                _LOGGER.debug("PIN successfully tested")
                self.config_data.update(user_input)
                return self.async_create_entry(
                    title=self.config_data[CONF_USERNAME], data=self.config_data
                )
        return self.async_show_form(step_id="pin", data_schema=PIN_SCHEMA, errors=error)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Subaru."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_ENABLED,
                    default=self.config_entry.options.get(CONF_UPDATE_ENABLED, False),
                ): cv.boolean,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
