"""Config flow for Ping (ICMP) integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util.network import is_ip_address

from .const import CONF_PING_COUNT, DEFAULT_PING_COUNT, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _clean_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Clean up the user input."""
    user_input[CONF_HOST] = user_input[CONF_HOST].strip()
    return user_input


class PingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ping."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                    }
                ),
            )

        user_input = _clean_user_input(user_input)
        if not is_ip_address(user_input[CONF_HOST]):
            self.async_abort(reason="invalid_ip_address")

        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        return self.async_create_entry(
            title=user_input[CONF_HOST],
            data={},
            options={
                **user_input,
                CONF_PING_COUNT: DEFAULT_PING_COUNT,
                CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME.seconds,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle an options flow for Ping."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=_clean_user_input(user_input))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self.config_entry.options[CONF_HOST]
                    ): str,
                    vol.Optional(
                        CONF_PING_COUNT,
                        default=self.config_entry.options[CONF_PING_COUNT],
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=100, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_CONSIDER_HOME,
                        default=self.config_entry.options.get(
                            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.seconds
                        ),
                    ): int,
                }
            ),
        )
