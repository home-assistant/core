"""Config flow for myLeviton decora_wifi."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .common import CommFailed, DecoraWifiPlatform, LoginFailed
from .const import CONF_TITLE, DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class DecoraWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Decora Wifi config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow class."""
        self.data = {}
        super().__init__()

    async def async_step_import(self, data=None) -> FlowResult:
        """Handle import from yaml."""
        self._async_abort_entries_match({CONF_USERNAME: data[CONF_USERNAME].lower()})
        _LOGGER.warning(
            "Configuring decora_wifi via yaml is deprecated; the configuration for"
            " %s is being migrated to a config entry and can be safely removed",
            data[CONF_USERNAME],
        )
        return await self.async_step_user_validate(data)

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
        # Proceed to prevalidation checks
        return await self.async_step_user_validate(user_input)

    async def async_step_user_validate(self, user_input=None) -> FlowResult:
        """Validate user-provided credentials and request re-entry if validation fails."""
        # Update data
        self.data.update(user_input)
        # Conduct pre-validation checks
        await self.async_set_unique_id(self.data[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()
        errors = await self._async_validate_credentials()
        if errors:
            # Re-show the form
            return self.async_show_form(
                step_id="user_validate",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_USERNAME, default=self.data[CONF_USERNAME]
                        ): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )
        return await self.async_step_user_finish()

    async def async_step_user_finish(self) -> FlowResult:
        """Finish the user config flow."""
        return self.async_create_entry(
            title=f"{CONF_TITLE} - {self.data[CONF_USERNAME]}", data=self.data
        )

    async def async_step_reauth(self, data) -> FlowResult:
        """Begin flow to re-authenticate an existing decora_wifi config."""
        self.data = dict(data)
        # Proceed to validation
        return self.async_show_form(
            step_id="reauth_validate",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
        )

    async def async_step_reauth_validate(self, user_input) -> FlowResult:
        """Validate reauth with user-provided password and request re-entry if validation fails."""
        # Update password record stored in data
        self.data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
        errors = await self._async_validate_credentials()
        if errors:
            # Re-show the form
            return self.async_show_form(
                step_id="reauth_validate",
                data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
                errors=errors,
            )
        return await self.async_step_reauth_finish()

    async def async_step_reauth_finish(self) -> FlowResult:
        """Finish the reauth config flow."""
        entry = await self.async_set_unique_id(self.data[CONF_USERNAME].lower())
        if entry:
            self.hass.config_entries.async_update_entry(
                entry, title=f"{CONF_TITLE} - {CONF_USERNAME}", data=self.data
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    async def _async_validate_credentials(self) -> dict[str, str]:
        """Call the myLeviton API to validate user-provided credentials."""
        session = None
        errors: dict[str, str] = {}
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
        if session:
            await self.hass.async_add_executor_job(session.teardown)
        return errors
