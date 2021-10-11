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
        """Initialize the config flow class."""
        self.data = {}
        self._finish_step = None
        super().__init__()

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle user-initiated setup config flow."""
        # Begin interactive credential input
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )
        # Update data
        self.data.update(user_input)
        # Conduct pre-validation checks
        await self.async_set_unique_id(self.data[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()
        # Set finish_step and proceed to validation
        self._finish_step = self.async_step_user_finish
        return await self.async_step_validate(None)

    async def async_step_validate(self, user_input=None) -> FlowResult:
        """Call the myLeviton API to validate user-provided credentials."""
        if user_input:
            self.data.update(user_input)
        session = None
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
            # Show the form with error message and direct the flow back to the retry step configured earlier
            return self.async_show_form(
                step_id="validate",
                data_schema=vol.Schema(
                    {vol.Required(CONF_PASSWORD, default=self.data[CONF_PASSWORD]): str}
                ),
                errors=errors,
            )
        # Login validated. Save the session in temp, then move on to the finish step.
        self.hass.data[DOMAIN][CONF_TEMPORARY] = session
        return await self._finish_step()

    async def async_step_user_finish(self) -> FlowResult:
        """Finish the user config flow."""
        return self.async_create_entry(
            title=f"{CONF_TITLE} - {self.data[CONF_USERNAME]}", data=self.data
        )

    async def async_step_reauth(self, data) -> FlowResult:
        """Begin flow to re-authenticate an existing decora_wifi config."""
        self.data = dict(data)
        # Set finish_step and retry_step_id and proceed to validation
        self._finish_step = self.async_step_reauth_finish
        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema(
                {vol.Required(CONF_PASSWORD, default=self.data[CONF_PASSWORD]): str}
            ),
        )

    async def async_step_reauth_finish(self) -> FlowResult:
        """Finish the reauth config flow."""
        entry = await self.async_set_unique_id(self.data[CONF_USERNAME].lower())
        if entry:
            self.hass.config_entries.async_update_entry(
                entry, title=f"{CONF_TITLE} - {CONF_USERNAME}", data=self.data
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")
