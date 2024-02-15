"""Config flow for Ping (ICMP) integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.util.network import is_ip_address

from .const import CONF_IMPORTED_BY, CONF_PING_COUNT, DEFAULT_PING_COUNT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ping."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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

    async def async_step_import(self, import_info: Mapping[str, Any]) -> FlowResult:
        """Import an entry."""

        to_import = {
            CONF_HOST: import_info[CONF_HOST],
            CONF_PING_COUNT: import_info[CONF_PING_COUNT],
            CONF_CONSIDER_HOME: import_info.get(
                CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME
            ).seconds,
        }
        title = import_info.get(CONF_NAME, import_info[CONF_HOST])

        self._async_abort_entries_match({CONF_HOST: to_import[CONF_HOST]})
        return self.async_create_entry(
            title=title,
            data={CONF_IMPORTED_BY: import_info[CONF_IMPORTED_BY]},
            options=to_import,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Ping."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

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
