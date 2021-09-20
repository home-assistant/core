"""Config flow for myLeviton decora_wifi."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME

from .common import CommFailed, DecoraWifiPlatform, LoginFailed
from .const import CONF_TITLE, DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class DecoraWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Decora Wifi config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.session = None
        self.data = {}
        self.entry = None

    async def async_step_user(self, user_input=None):
        """Prompt for user input to setup decora_wifi."""

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
        self.entry = await self.async_set_unique_id(self.data[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()

        # Attempt to log in with the credentials provided by the user.
        errors = {}
        try:
            self.session = await DecoraWifiPlatform.async_setup_decora_wifi(
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

        # Normal config entry setup
        return self.async_create_entry(
            title=f"{CONF_TITLE} - {self.data[CONF_USERNAME]}", data=self.data
        )

    async def async_step_reauth(self, user_input=None):
        """Re-authenticate a user."""
        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
        self.data = {
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
        }

        self.entry = await self.async_set_unique_id(self.data[CONF_USERNAME].lower())

        errors = {}
        try:
            self.session = await DecoraWifiPlatform.async_setup_decora_wifi(
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

        # Login attempt succeeded. Update the config entry.
        self.hass.config_entries.async_update_entry(
            self.entry, title=f"{CONF_TITLE} - {CONF_USERNAME}", data=self.data
        )
        await self.hass.config_entries.async_reload(self.entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    async def async_step_import(self, user_input=None):
        """Import user."""
        return await self.async_step_user(user_input)
