"""Config flow to configure Blink."""
import logging

from blinkpy.auth import Auth, LoginError, TokenRefreshFailed
from blinkpy.blinkpy import Blink, BlinkSetupError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components.blink.const import (
    DEFAULT_SCAN_INTERVAL,
    DEVICE_ID,
    DOMAIN,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)


def validate_input(hass: core.HomeAssistant, auth):
    """Validate the user input allows us to connect."""
    try:
        auth.startup()
    except (LoginError, TokenRefreshFailed) as err:
        raise InvalidAuth from err
    if auth.check_key_required():
        raise Require2FA


def _send_blink_2fa_pin(auth, pin):
    """Send 2FA pin to blink servers."""
    blink = Blink()
    blink.auth = auth
    blink.setup_urls()
    return auth.send_auth_key(blink, pin)


class BlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Blink config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the blink flow."""
        self.auth = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return BlinkOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        data = {CONF_USERNAME: "", CONF_PASSWORD: "", "device_id": DEVICE_ID}
        if user_input is not None:
            data[CONF_USERNAME] = user_input["username"]
            data[CONF_PASSWORD] = user_input["password"]

            self.auth = Auth(data, no_prompt=True)
            await self.async_set_unique_id(data[CONF_USERNAME])

            try:
                await self.hass.async_add_executor_job(
                    validate_input, self.hass, self.auth
                )
                return self._async_finish_flow()
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
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_2fa(self, user_input=None):
        """Handle 2FA step."""
        errors = {}
        if user_input is not None:
            pin = user_input.get(CONF_PIN)
            try:
                valid_token = await self.hass.async_add_executor_job(
                    _send_blink_2fa_pin, self.auth, pin
                )
            except BlinkSetupError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            else:
                if valid_token:
                    return self._async_finish_flow()
                errors["base"] = "invalid_access_token"

        return self.async_show_form(
            step_id="2fa",
            data_schema=vol.Schema(
                {vol.Optional("pin"): vol.All(str, vol.Length(min=1))}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Perform reauth upon migration of old entries."""
        return await self.async_step_user(entry_data)

    @callback
    def _async_finish_flow(self):
        """Finish with setup."""
        return self.async_create_entry(title=DOMAIN, data=self.auth.login_attributes)


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
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=scan_interval,
                    ): int
                }
            ),
        )


class Require2FA(exceptions.HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
