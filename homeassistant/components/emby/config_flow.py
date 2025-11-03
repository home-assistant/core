"""Config flow for Emby integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.helpers import selector
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SSL, DEFAULT_SSL_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                step=1, mode=selector.NumberSelectorMode.BOX, min=1, max=65535
            )
        ),
        vol.Required(CONF_SSL, default=DEFAULT_SSL): selector.BooleanSelector(),
    }
)


class EmbyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emby."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                unique_id=f"{user_input[CONF_HOST]}:{int(user_input[CONF_PORT])}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{user_input[CONF_HOST]}:{int(user_input[CONF_PORT])}",
                data=user_input,
            )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: ConfigType) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        api_key = import_data[CONF_API_KEY]
        host = import_data.get(CONF_HOST) or DEFAULT_HOST
        ssl = import_data.get(CONF_SSL) or DEFAULT_SSL
        port = int(import_data.get(CONF_PORT) or DEFAULT_PORT)
        if ssl and port == DEFAULT_PORT:
            port = DEFAULT_SSL_PORT
        await self.async_set_unique_id(unique_id=f"{host}:{port}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{host}:{port}",
            data={
                CONF_API_KEY: api_key,
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_SSL: ssl,
            },
        )
