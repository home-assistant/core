"""Config flow for the Energy Tracker integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
import voluptuous as vol

from .const import CONF_API_TOKEN, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): vol.All(str, vol.Strip, vol.Length(min=1)),
        vol.Required(CONF_API_TOKEN): vol.All(str, vol.Strip, vol.Length(min=1)),
    }
)

STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): vol.All(str, vol.Strip, vol.Length(min=1)),
        vol.Optional(CONF_API_TOKEN): vol.All(str, vol.Strip, vol.Length(min=1)),
    }
)


class EnergyTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow handler for the Energy Tracker integration.

    This class manages the configuration and reconfiguration steps for the integration.
    """

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            token = user_input[CONF_API_TOKEN].strip()

            await self.async_set_unique_id(token)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={CONF_API_TOKEN: token},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            new_name_input = user_input.get(CONF_NAME)
            new_name = new_name_input.strip() if new_name_input else entry.title

            new_token_input = user_input.get(CONF_API_TOKEN)
            new_token = (
                new_token_input.strip()
                if new_token_input
                else entry.data[CONF_API_TOKEN]
            )

            if new_token != entry.data[CONF_API_TOKEN]:
                await self.async_set_unique_id(new_token)
                self._abort_if_unique_id_configured()
                self.hass.config_entries.async_update_entry(entry, unique_id=new_token)

            return self.async_update_reload_and_abort(
                entry,
                title=new_name,
                data={CONF_API_TOKEN: new_token},
                reason="reconfigure_successful",
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_RECONFIGURE_DATA_SCHEMA,
        )
