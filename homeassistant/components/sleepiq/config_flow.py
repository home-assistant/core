"""Config flow to configure SleepIQ component."""
from __future__ import annotations

from typing import Any

from sleepyq import Sleepyq
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class SleepIQFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a SleepIQ config flow."""

    VERSION = 1

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a SleepIQ account as a config entry.

        This flow is triggered by 'async_setup' for configured accounts.
        """
        return self.async_create_entry(
            title=import_config[CONF_USERNAME], data=import_config
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            # Don't allow multiple instances with the same username
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            valid = await self.hass.async_add_executor_job(try_connection, user_input)
            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

            errors["base"] = "cannot_connect"

        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=60): int,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors,
            last_step=True,
        )


def try_connection(user_input: dict[str, Any]) -> bool:
    """Test if the given credentials can successfully login to SleepIQ."""

    client = Sleepyq(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

    try:
        client.login()
    except ValueError:
        return False

    return True
