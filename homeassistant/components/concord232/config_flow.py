"""Config flow for the Concord232 integration."""

import logging
from typing import Any, override

from concord232 import client as concord232_client
import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_MODE, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import build_url
from .const import DEFAULT_MODE, DEFAULT_PORT, DOMAIN, MODE_AUDIBLE, MODE_SILENT
from .coordinator import Concord232ConfigEntry

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CODE): str,
        vol.Required(CONF_MODE, default=DEFAULT_MODE): SelectSelector(
            SelectSelectorConfig(
                options=[MODE_AUDIBLE, MODE_SILENT],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="arm_home_mode",
            )
        ),
    }
)


def _try_connect(url: str) -> bool:
    """Return True when the Concord232 server answers."""
    try:
        concord232_client.Client(url).list_partitions()
    except requests.exceptions.RequestException:
        return False
    return True


class Concord232ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Concord232 config flow."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: Concord232ConfigEntry,
    ) -> Concord232OptionsFlow:
        """Create the options flow."""
        return Concord232OptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            url = build_url(user_input[CONF_HOST], user_input[CONF_PORT])
            if await self.hass.async_add_executor_job(_try_connect, url):
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from YAML platform configuration."""
        data = {
            CONF_HOST: import_data[CONF_HOST],
            CONF_PORT: import_data[CONF_PORT],
        }
        self._async_abort_entries_match(
            {CONF_HOST: data[CONF_HOST], CONF_PORT: data[CONF_PORT]}
        )
        url = build_url(data[CONF_HOST], data[CONF_PORT])
        if not await self.hass.async_add_executor_job(_try_connect, url):
            return self.async_abort(reason="cannot_connect")

        options: dict[str, Any] = {}
        if CONF_CODE in import_data:
            options[CONF_CODE] = import_data[CONF_CODE]
        if CONF_MODE in import_data:
            options[CONF_MODE] = import_data[CONF_MODE]

        return self.async_create_entry(
            title=import_data.get(CONF_NAME, data[CONF_HOST]),
            data=data,
            options=options,
        )


class Concord232OptionsFlow(OptionsFlow):
    """Handle Concord232 options (arm code and arm-home mode)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, dict(self.config_entry.options)
            ),
        )
