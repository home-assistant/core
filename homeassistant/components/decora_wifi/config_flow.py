"""Config flow for myLeviton decora_wifi."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .common import CommFailed, DecoraWifiPlatform, LoginFailed
from .const import CONF_TEMPORARY, CONF_TITLE, DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class DecoraWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Decora Wifi config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.data = {}
        super().__init__()

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Prompt for user input to setup decora_wifi."""
        session = None

        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

        if user_input is None:
            # Show the form requesting the Username and Password for Decora Wifi
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(data_schema)
            )

        # Update flow state
        self.data.update(user_input)

        # Get user from existing entry and abort if already setup.
        await self.async_set_unique_id(self.data[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()

        # Attempt to log in with the credentials provided by the user.
        errors = {}
        try:
            session = await DecoraWifiPlatform.async_setup_decora_wifi(
                self.hass,
                email=self.data[CONF_USERNAME],
                password=self.data[CONF_PASSWORD],
            )
        except LoginFailed:
            errors["base"] = "invalid_auth"
        except CommFailed:
            errors["base"] = "cannot_connect"
        if errors:
            # Re-show the dialog w/ an error message.
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(data_schema), errors=errors
            )
        # Use the unique user id from the API to identify the platform entity
        self.data[CONF_ID] = self.session.unique_id

        # Save the new session in temporary storage so that async_setup_entry doesn't need to re-authenticate.
        self.hass.data[DOMAIN][CONF_TEMPORARY] = session
        # Normal config entry setup
        return self.async_create_entry(
            title=f"{CONF_TITLE} - {self.data[CONF_USERNAME]}", data=self.data
        )

    async def async_step_reauth(self, user_input=None) -> FlowResult:
        """Re-authenticate a user."""
        session = None

        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

        if user_input is None:
            return self.async_show_form(
                step_id="reauth", data_schema=vol.Schema(data_schema)
            )

        self.data = {
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
        }

        entry = await self.async_set_unique_id(self.data[CONF_USERNAME].lower())
        if not entry:
            return self.async_abort(reason="reauth_failed")

        # Validate the user input and re-show the dialog if there are errors.
        errors = {}
        try:
            session = await DecoraWifiPlatform.async_setup_decora_wifi(
                self.hass,
                email=self.data[CONF_USERNAME],
                password=self.data[CONF_PASSWORD],
            )
        except LoginFailed:
            errors["base"] = "invalid_auth"
        except CommFailed:
            errors["base"] = "cannot_connect"
        if errors:
            return self.async_show_form(
                step_id="reauth", data_schema=vol.Schema(data_schema), errors=errors
            )

        # Login validated. Save the session in temp, then update and reload the config entry.
        self.hass.data[DOMAIN][CONF_TEMPORARY] = session
        self.hass.config_entries.async_update_entry(
            entry, title=f"{CONF_TITLE} - {CONF_USERNAME}", data=self.data
        )
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    async def async_step_import(self, user_input=None):
        """Import user."""
        return await self.async_step_user(user_input)
