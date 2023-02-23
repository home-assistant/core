"""Config flow for SPC."""
from __future__ import annotations

import logging
from typing import Any

from pyspcwebgw import SpcWebGateway
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_API_URL, CONF_WS_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = {
    vol.Required(CONF_WS_URL): str,
    vol.Required(CONF_API_URL): str,
}


class SpcConnectionFailure(Exception):
    """Raised during connection failure in config validation."""


async def _validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> SpcWebGateway:
    """Validate the user input allows us to connect."""

    spc = SpcWebGateway(
        loop=hass.loop,
        session=async_create_clientsession(hass),
        api_url=user_input.get(CONF_API_URL),
        ws_url=user_input.get(CONF_WS_URL),
        async_callback=lambda _: ...,
    )

    if not await spc.async_load_parameters():
        raise SpcConnectionFailure()

    return spc


class SPCConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SPC."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self.entry: ConfigEntry | None = None

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_URL] == import_config[CONF_API_URL]:
                return self.async_abort(reason="already_configured")

        return await self.async_step_user(import_config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_API_URL: user_input[CONF_API_URL],
                    CONF_WS_URL: user_input[CONF_WS_URL],
                }
            )
            try:
                spc = await _validate_input(self.hass, user_input)
            except SpcConnectionFailure:
                errors = {"base": "failed_to_connect"}
            except Exception:  # pylint: disable=broad-except
                return self.async_abort(reason="unknown")
            else:
                return self.async_create_entry(
                    title=f"{spc.info['type']} - {spc.info['sn']}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(CONFIG_SCHEMA),
            errors=errors,
        )
