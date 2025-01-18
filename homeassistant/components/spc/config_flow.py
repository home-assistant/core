"""Config flow for SPC integration."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError
from pyspcwebgw import SpcWebGateway
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import aiohttp_client

from . import CONF_API_URL, CONF_WS_URL, DOMAIN


class SpcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SPC."""

    VERSION = 1

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_URL] == import_config[CONF_API_URL]:
                return self.async_abort(reason="already_configured")

        return await self.async_step_user(import_config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                session = aiohttp_client.async_get_clientsession(self.hass)
                spc = SpcWebGateway(
                    loop=self.hass.loop,
                    session=session,
                    api_url=user_input[CONF_API_URL],
                    ws_url=user_input[CONF_WS_URL],
                    async_callback=lambda: None,
                )

                if await spc.async_load_parameters():
                    return self.async_create_entry(
                        title=f"{spc.info['type']} - {spc.info['sn']}",
                        data={
                            CONF_API_URL: user_input[CONF_API_URL],
                            CONF_WS_URL: user_input[CONF_WS_URL],
                        },
                    )
                errors["base"] = "cannot_connect"
            except ClientError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_URL): str,
                    vol.Required(CONF_WS_URL): str,
                }
            ),
            errors=errors,
        )
