"""Config flow for WMS WebControl pro API integration."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from wmspro.webcontrol import WebControlPro

from homeassistant.components import dhcp
from homeassistant.components.dhcp import DhcpServiceInfo
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

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle the DHCP discovery step."""
        unique_id = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(unique_id)

        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, unique_id
        )
        if entry:
            try:  # Check if current host is a valid IP address
                ipaddress.ip_address(entry.data[CONF_HOST])
            except ValueError:  # Do not touch name-based host
                return self.async_abort(reason="already_configured")
            else:  # Update existing host with new IP address
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: discovery_info.ip}
                )

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if not entry.unique_id and entry.data[CONF_HOST] in (
                discovery_info.hostname,
                discovery_info.ip,
            ):
                self.hass.config_entries.async_update_entry(entry, unique_id=unique_id)
                return self.async_abort(reason="already_configured")

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user-based step."""
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
                    await hub.refresh()
                    rooms = set(hub.rooms.keys())
                    for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
                        if (
                            entry.runtime_data
                            and entry.runtime_data.rooms
                            and set(entry.runtime_data.rooms.keys()) == rooms
                        ):
                            return self.async_abort(reason="already_configured")
                    return self.async_create_entry(title=host, data=user_input)

        if self.source == dhcp.DOMAIN:
            discovery_info: DhcpServiceInfo = self.init_data
            data_values = {CONF_HOST: discovery_info.ip}
        else:
            data_values = {CONF_HOST: SUGGESTED_HOST}

        self.context["title_placeholders"] = data_values
        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, data_values
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
