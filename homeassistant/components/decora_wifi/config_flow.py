"""Config flow for myLeviton decora_wifi."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SOURCE, CONF_USERNAME

from .common import DecoraWifiCommFailed, DecoraWifiLoginFailed, DecoraWifiPlatform
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
        errors = {}

        if user_input is not None:
            # Update flow state
            self.data.update(user_input)

            # Get user from existing entry and abort if already setup.
            self.entry = await self.async_set_unique_id(self.data[CONF_USERNAME])
            if self.context[CONF_SOURCE] != config_entries.SOURCE_REAUTH:
                self._abort_if_unique_id_configured()

            try:
                # Attempt to log in with the credentials provided by the user.
                self.session = await DecoraWifiPlatform.async_login(
                    self.hass,
                    email=self.data[CONF_USERNAME],
                    password=self.data[CONF_PASSWORD],
                )
            except DecoraWifiLoginFailed:
                errors["base"] = "Login Failed. Check Credentials."
            except DecoraWifiCommFailed:
                errors["base"] = "Communication with Decora Wifi Service Failed."

            if not errors:
                # Complete the entry setup.
                if self.context[CONF_SOURCE] == config_entries.SOURCE_REAUTH:
                    # Reauth case
                    self.hass.config_entries.async_update_entry(
                        self.entry, title=CONF_TITLE, data=self.data
                    )
                    await self.hass.config_entries.async_reload(self.entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                else:
                    # Normal config entry setup
                    return self.async_create_entry(title=CONF_TITLE, data=self.data)

        # Show the form requesting the Username and Password for Decora Wifi
        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))

    async def async_step_reauth(self, user_input=None):
        """Re-authenticate a user."""
        data = {
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
        }
        return await self.async_step_user(data)

    async def async_step_import(self, user_input=None):
        """Import user."""
        return await self.async_step_user(user_input)
