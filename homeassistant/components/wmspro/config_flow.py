"""Config flow for WMS WebControl pro API integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from wmspro.webcontrol import WebControlPro

from homeassistant.components import dhcp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SUGGESTED_HOST

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, description={"suggested_value": SUGGESTED_HOST}): str,
    }
)


async def setup_and_verify(hass: HomeAssistant, host: str) -> WebControlPro:
    """Set up and verify the connection to the wmspro."""
    session = async_get_clientsession(hass)

    hub = WebControlPro(host, session)
    try:
        pong = await hub.ping()
    except aiohttp.ClientError as err:
        raise CannotConnect from err
    if not pong:
        raise CannotConnect

    return hub


class WebControlProConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for wmspro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = user_input[CONF_HOST]
                await setup_and_verify(self.hass, host)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=host, data=user_input)

        data_schema = STEP_USER_DATA_SCHEMA
        if self.source == dhcp.DOMAIN:
            placeholders = {CONF_HOST: self.init_data.hostname}
            self.context["title_placeholders"] = placeholders
            data_schema = self.add_suggested_values_to_schema(data_schema, placeholders)

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
