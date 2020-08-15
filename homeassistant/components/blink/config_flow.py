"""Config flow to configure Blink."""
import logging

from blinkpy.blinkpy import Blink
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback

from .const import DEFAULT_OFFSET, DEFAULT_SCAN_INTERVAL, DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, blink):
    """Validate the user input allows us to connect."""
    response = await hass.async_add_executor_job(blink.get_auth_token)
    if not response:
        raise InvalidAuth
    if blink.key_required:
        raise Require2FA

    return blink.login_response


class BlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Blink config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the blink flow."""
        self.blink = None
        self.data = {
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            "login_response": None,
        }

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return BlinkOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            self.data[CONF_USERNAME] = user_input["username"]
            self.data[CONF_PASSWORD] = user_input["password"]

            await self.async_set_unique_id(self.data[CONF_USERNAME])

            if CONF_SCAN_INTERVAL in user_input:
                self.data[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]

            self.blink = Blink(
                username=self.data[CONF_USERNAME],
                password=self.data[CONF_PASSWORD],
                motion_interval=DEFAULT_OFFSET,
                legacy_subdomain=False,
                no_prompt=True,
                device_id=DEVICE_ID,
            )

            try:
                response = await validate_input(self.hass, self.blink)
                self.data["login_response"] = response
                return self.async_create_entry(title=DOMAIN, data=self.data,)
            except Require2FA:
                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = {
            vol.Required("username"): str,
            vol.Required("password"): str,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors,
        )

    async def async_step_2fa(self, user_input=None):
        """Handle 2FA step."""
        if user_input is not None:
            pin = user_input.get(CONF_PIN)
            if await self.hass.async_add_executor_job(
                self.blink.login_handler.send_auth_key, self.blink, pin
            ):
                return await self.async_step_user(user_input=self.data)

        return self.async_show_form(
            step_id="2fa",
            data_schema=vol.Schema(
                {vol.Optional("pin"): vol.All(str, vol.Length(min=1))}
            ),
        )

    async def async_step_import(self, import_data):
        """Import blink config from configuration.yaml."""
        return await self.async_step_user(import_data)


class BlinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Blink options."""

    def __init__(self, config_entry):
        """Initialize Blink options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.blink = None

    async def async_step_init(self, user_input=None):
        """Manage the Blink options."""
        self.blink = self.hass.data[DOMAIN][self.config_entry.entry_id]
        self.options[CONF_SCAN_INTERVAL] = self.blink.refresh_rate

        return await self.async_step_simple_options()

    async def async_step_simple_options(self, user_input=None):
        """For simple options."""
        if user_input is not None:
            self.options.update(user_input)
            self.blink.refresh_rate = user_input[CONF_SCAN_INTERVAL]
            return self.async_create_entry(title="", data=self.options)

        options = self.config_entry.options
        scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        return self.async_show_form(
            step_id="simple_options",
            data_schema=vol.Schema(
                {vol.Optional(CONF_SCAN_INTERVAL, default=scan_interval,): int}
            ),
        )


class Require2FA(exceptions.HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
