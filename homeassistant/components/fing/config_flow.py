"""Config flow file."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback

from .const import AGENT_IP, AGENT_SECRET, DOMAIN


def _get_data_schema(
    hass: HomeAssistant, config_entry: ConfigEntry | None = None
) -> vol.Schema:
    """Get a schema with default values."""

    if config_entry is None:
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default="TEST"): str,
                vol.Required(AGENT_IP): str,
                vol.Required(AGENT_SECRET): str,
            }
        )

    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=config_entry.data.get(CONF_NAME)): str,
            vol.Required(AGENT_IP, default=config_entry.data.get(AGENT_IP)): str,
            vol.Required(
                AGENT_SECRET, default=config_entry.data.get(AGENT_SECRET)
            ): str,
        }
    )


class FingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Async step user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=_get_data_schema(self.hass), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for Met."""
        return FingOptionsFlow(config_entry)


class FingOptionsFlow(OptionsFlowWithConfigEntry):
    """Options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure options."""

        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=user_input
            )
            return self.async_create_entry(title="init", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_get_data_schema(self.hass, config_entry=self._config_entry),
        )
