"""Config flow for Radio Thermostat integration."""
from __future__ import annotations

import logging
from socket import timeout
from typing import Any
from urllib.error import URLError

from radiotherm.validate import RadiothermTstatError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .data import RadioThermInitData, async_get_init_data

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


async def validate_connection(hass: HomeAssistant, host: str) -> RadioThermInitData:
    """Validate the connection."""
    try:
        return await async_get_init_data(hass, host)
    except (timeout, RadiothermTstatError, URLError, OSError) as ex:
        raise CannotConnect(f"Failed to connect to {host}: {ex}") from ex


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radio Thermostat."""

    VERSION = 1

    def __init__(self):
        """Initialize ConfigFlow."""
        self.discovered_ip: str | None = None
        self.discovered_init_data: RadioThermInitData | None = None

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Discover via DHCP."""
        self._async_abort_entries_match({CONF_HOST: discovery_info.ip})
        try:
            init_data = await validate_connection(self.hass, discovery_info.ip)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(init_data.mac)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info.ip}, reload_on_update=False
        )
        self.discovered_init_data = init_data
        self.discovered_ip = discovery_info.ip
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Attempt to confirm."""
        ip_address = self.discovered_ip
        init_data = self.discovered_init_data
        assert ip_address is not None
        assert init_data is not None
        if user_input is not None:
            return self.async_create_entry(
                title=init_data.name,
                data={CONF_HOST: ip_address},
            )

        self._set_confirm_only()
        placeholders = {
            "name": init_data.name,
            "host": self.discovered_ip,
            "model": init_data.model or "Unknown",
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="confirm",
            description_placeholders=placeholders,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Import from yaml."""
        host = import_info[CONF_HOST]
        self._async_abort_entries_match({CONF_HOST: host})
        _LOGGER.debug("Importing entry for host: %s", host)
        try:
            init_data = await validate_connection(self.hass, host)
        except CannotConnect as ex:
            _LOGGER.debug("Importing failed for %s", host, exc_info=ex)
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(init_data.mac, raise_on_progress=False)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: host}, reload_on_update=False
        )
        return self.async_create_entry(
            title=init_data.name,
            data={CONF_HOST: import_info[CONF_HOST]},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                init_data = await validate_connection(self.hass, user_input[CONF_HOST])
            except CannotConnect:
                errors[CONF_HOST] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(init_data.mac, raise_on_progress=False)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]},
                    reload_on_update=False,
                )
                return self.async_create_entry(
                    title=init_data.name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
