"""Config flow for the Energy Tracker integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_API_TOKEN, DOMAIN


class EnergyTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Config flow handler for the Energy Tracker integration.

    This class manages the configuration and reconfiguration steps for the integration.
    """

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()

            if not token:
                errors["api_token"] = "empty_token"

            if not errors:
                await self.async_set_unique_id(token)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Energy Tracker Account",
                    data={CONF_API_TOKEN: token},
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            new_token_input = user_input.get(CONF_API_TOKEN)
            new_token = (
                new_token_input.strip()
                if new_token_input
                else entry.data[CONF_API_TOKEN]
            )

            if new_token_input is not None and not new_token:
                errors["api_token"] = "empty_token"

            if not errors:
                if new_token != entry.data[CONF_API_TOKEN]:
                    await self.async_set_unique_id(new_token)
                    self._abort_if_unique_id_configured()
                    self.hass.config_entries.async_update_entry(
                        entry, unique_id=new_token
                    )

                return self.async_update_reload_and_abort(
                    entry,
                    data={CONF_API_TOKEN: new_token},
                    reason="reconfigure_successful",
                )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_API_TOKEN): str,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )
