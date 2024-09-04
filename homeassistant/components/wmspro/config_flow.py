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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, SUGGESTED_HOST

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class WebControlProConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for wmspro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            hub = WebControlPro(host, session)
            try:
                pong = await hub.ping()
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not pong:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=host, data=user_input)

        if self.source == dhcp.DOMAIN:
            await self.async_set_unique_id(format_mac(self.init_data.macaddress))
            data_values = {CONF_HOST: self.init_data.hostname}
            self._abort_if_unique_id_configured(updates=data_values)
        else:
            data_values = {CONF_HOST: SUGGESTED_HOST}

        self.context["title_placeholders"] = data_values
        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, data_values
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
