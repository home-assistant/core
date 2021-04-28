"""Config Flow for Hive."""

from apyhiveapi import Auth
from apyhiveapi.helper.hive_exceptions import (
    HiveApiError,
    HiveInvalid2FACode,
    HiveInvalidPassword,
    HiveInvalidUsername,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback

from .const import CONF_CODE, CONFIG_ENTRY_VERSION, DOMAIN


class HiveFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hive config flow."""

    VERSION = CONFIG_ENTRY_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.hive_auth = None
        self.data = {}
        self.tokens = {}
        self.entry = None

    async def async_step_user(self, user_input=None):
        """Prompt user input. Create or edit entry."""
        errors = {}
        # Login to Hive with user data.
        if user_input is not None:
            self.data.update(user_input)
            self.hive_auth = Auth(
                username=self.data[CONF_USERNAME], password=self.data[CONF_PASSWORD]
            )

            # Get user from existing entry and abort if already setup
            self.entry = await self.async_set_unique_id(self.data[CONF_USERNAME])
            if self.context["source"] != config_entries.SOURCE_REAUTH:
                self._abort_if_unique_id_configured()

            # Login to the Hive.
            try:
                self.tokens = await self.hive_auth.login()
            except HiveInvalidUsername:
                errors["base"] = "invalid_username"
            except HiveInvalidPassword:
                errors["base"] = "invalid_password"
            except HiveApiError:
                errors["base"] = "no_internet_available"

            if self.tokens.get("ChallengeName") == "SMS_MFA":
                # Complete SMS 2FA.
                return await self.async_step_2fa()

            if not errors:
                # Complete the entry setup.
                try:
                    return await self.async_setup_hive_entry()
                except UnknownHiveError:
                    errors["base"] = "unknown"

        # Show User Input form.
        schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_2fa(self, user_input=None):
        """Handle 2fa step."""
        errors = {}

        if user_input and user_input["2fa"] == "0000":
            self.tokens = await self.hive_auth.login()
        elif user_input:
            try:
                self.tokens = await self.hive_auth.sms_2fa(
                    user_input["2fa"], self.tokens
                )
            except HiveInvalid2FACode:
                errors["base"] = "invalid_code"
            except HiveApiError:
                errors["base"] = "no_internet_available"

            if not errors:
                try:
                    return await self.async_setup_hive_entry()
                except UnknownHiveError:
                    errors["base"] = "unknown"

        schema = vol.Schema({vol.Required(CONF_CODE): str})
        return self.async_show_form(step_id="2fa", data_schema=schema, errors=errors)

    async def async_setup_hive_entry(self):
        """Finish setup and create the config entry."""

        if "AuthenticationResult" not in self.tokens:
            raise UnknownHiveError

        # Setup the config entry
        self.data["tokens"] = self.tokens
        if self.context["source"] == config_entries.SOURCE_REAUTH:
            self.hass.config_entries.async_update_entry(
                self.entry, title=self.data["username"], data=self.data
            )
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        return self.async_create_entry(title=self.data["username"], data=self.data)

    async def async_step_reauth(self, user_input=None):
        """Re Authenticate a user."""
        data = {
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
        }
        return await self.async_step_user(data)

    async def async_step_import(self, user_input=None):
        """Import user."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Hive options callback."""
        return HiveOptionsFlowHandler(config_entry)


class HiveOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for Hive."""

    def __init__(self, config_entry):
        """Initialize Hive options flow."""
        self.hive = None
        self.config_entry = config_entry
        self.interval = config_entry.options.get(CONF_SCAN_INTERVAL, 120)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self.hive = self.hass.data["hive"][self.config_entry.entry_id]
        errors = {}
        if user_input is not None:
            new_interval = user_input.get(CONF_SCAN_INTERVAL)
            await self.hive.updateInterval(new_interval)
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=self.interval): vol.All(
                    vol.Coerce(int), vol.Range(min=30)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class UnknownHiveError(Exception):
    """Catch unknown hive error."""
