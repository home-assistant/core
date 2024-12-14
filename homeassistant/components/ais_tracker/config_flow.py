"""Config flow for AIS tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PORT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_MMSIS, DEFAULT_PORT, DOMAIN


class AisTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AIS tracker."""

    VERSION = 1
    _config_entry: ConfigEntry

    def show_user_form(
        self, user_input: dict[str, Any] | None = None, step_id: str = "user"
    ) -> ConfigFlowResult:
        """Show the user form."""
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): cv.port,
                    vol.Required(
                        CONF_MMSIS, default=user_input.get(CONF_MMSIS, [])
                    ): SelectSelector(
                        SelectSelectorConfig(
                            multiple=True,
                            custom_value=True,
                            mode=SelectSelectorMode.LIST,
                            options=[],
                        )
                    ),
                }
            ),
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the user step."""
        if user_input is not None:
            self._async_abort_entries_match({CONF_PORT: user_input[CONF_PORT]})
            return self.async_create_entry(
                title=f"AIS listener on {user_input[CONF_PORT]}", data=user_input
            )

        return self.show_user_form()

    async def async_step_reconfigure(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure step."""
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if TYPE_CHECKING:
            assert config_entry is not None
        self._config_entry = config_entry
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure confirm step."""
        if not user_input:
            return self.show_user_form(
                user_input={**self._config_entry.data}, step_id="reconfigure_confirm"
            )

        return self.async_update_reload_and_abort(
            self._config_entry, data=user_input, reason="reconfigure_successful"
        )
