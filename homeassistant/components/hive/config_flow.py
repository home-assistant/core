"""Config Flow for Hive."""

from pyhiveapi import HiveAuthAsync, Session
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
        self.data = {"options": {}}
        self.tokens = None
        self.entry = None

    async def async_step_user(self, user_input=None):
        """Prompt user input. Create or edit entry."""
        errors = {}
        # Login to Hive with user data.
        if user_input is not None:
            self.data.update(user_input)
            self.hive_auth = HiveAuthAsync(
                username=self.data[CONF_USERNAME], password=self.data[CONF_PASSWORD]
            )

            # Get user from existing entry and abort if already setup
            for entry in self._async_current_entries():
                if (
                    entry.data.get(CONF_USERNAME) == self.data[CONF_USERNAME]
                    and not self.entry
                ):
                    return self.async_abort(reason="already_configured")

            # Login to the Hive.
            self.tokens = await self.hive_auth.login()

            # Check if the login was successful.
            if self.tokens == "INVALID_USER":
                errors["base"] = "invalid_username"
            elif self.tokens == "INVALID_PASSWORD":
                errors["base"] = "invalid_password"
            elif self.tokens == "CONNECTION_ERROR":
                errors["base"] = "no_internet_available"
            else:
                # Check if SMS 2fa is required.
                if self.tokens.get("ChallengeName") == "SMS_MFA":
                    # Complete SMS 2FA.
                    return await self.async_step_2fa()

                # Complete the entry setup.
                return await self.async_step_finish()

        # Show User Input form.
        schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_2fa(self, user_input=None):
        """Handle 2fa step."""
        errors = {}
        result = None

        if user_input and user_input["2fa"] == "0000":
            self.tokens = await self.hive_auth.login()
        elif user_input:
            result = await self.hive_auth.sms_2fa(user_input["2fa"], self.tokens)

            if result == "INVALID_CODE":
                errors["base"] = "invalid_code"
            elif result == "CONNECTION_ERROR":
                errors["base"] = "no_internet_available"
            elif "AuthenticationResult" in result:
                self.tokens = result
                return await self.async_step_finish()

        schema = vol.Schema({vol.Required(CONF_CODE): str})

        return self.async_show_form(step_id="2fa", data_schema=schema, errors=errors)

    async def async_step_finish(self):
        """Finish setup and create the config entry."""
        self.data["tokens"] = self.tokens.get("AuthenticationResult")

        if "AccessToken" in self.data["tokens"]:
            # Setup the config entry
            if self.entry:
                self.hass.config_entries.async_update_entry(
                    self.entry, title=self.data["username"], data=self.data
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_sucessfull")
            return self.async_create_entry(title=self.data["username"], data=self.data)
        return self.async_abort(reason="unknown")

    async def async_step_reauth(self, user_input=None):
        """Re Authenticate a user."""
        errors = {}

        if user_input is not None:
            for entry in self._async_current_entries():
                if entry.unique_id == self.unique_id:
                    self.entry = entry
                    return await self.async_step_user(user_input)
                return self.async_abort(reason="unknown_entry")

        schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )

        return self.async_show_form(step_id="reauth", data_schema=schema, errors=errors)

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
        self.hive = Session()
        self.interval = config_entry.options.get(CONF_SCAN_INTERVAL, 120)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            new_interval = user_input.get(CONF_SCAN_INTERVAL)
            if new_interval < 30:
                new_interval = 30
                user_input[CONF_SCAN_INTERVAL] = new_interval

            await self.hive.updateInterval(new_interval)
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {vol.Optional(CONF_SCAN_INTERVAL, default=self.interval): int}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
