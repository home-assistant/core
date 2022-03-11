"""Config flow to configure the Uptime Kuma integration."""
from uptime_kuma_monitor import UptimeKumaError, UptimeKumaMonitor
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=443): vol.Coerce(int),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


class UptimeKumaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an Uptime Kuma config flow."""

    VERSION = 1

    async def _show_setup_form(self, errors: dict = None) -> FlowResult:
        """Show the setup form to the user."""

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors or {},
        )

    async def async_step_user(self, user_input: dict = None) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )

        errors = {}

        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)
        utkm = await self.hass.async_add_executor_job(
            UptimeKumaMonitor,
            f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
            username,
            password,
            user_input[CONF_VERIFY_SSL],
        )

        try:
            await self.hass.async_add_executor_job(utkm.update)
        except UptimeKumaError:
            errors["base"] = "cannot_connect"
            return await self._show_setup_form(errors)

        return self.async_create_entry(
            title=user_input[CONF_HOST],
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_PORT: user_input[CONF_PORT],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            },
        )
