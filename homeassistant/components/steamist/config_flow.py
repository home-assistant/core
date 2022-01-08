"""Config flow for Steamist integration."""
from __future__ import annotations

import logging
from typing import Any

from aiosteamist import Steamist
from discovery30303 import Device30303, normalize_mac
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONNECTION_EXCEPTIONS, DOMAIN
from .discovery import async_discover_device, async_update_entry_from_discovery

_LOGGER = logging.getLogger(__name__)

MODEL_450_HOSTNAME_PREFIX = "MY450-"
MODEL_550_HOSTNAME_PREFIX = "MY550-"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Steamist."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, Device30303] = {}
        self._discovered_device: Device30303 | None = None

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        self._discovered_device = Device30303(
            ipaddress=discovery_info.ip,
            name="",
            mac=normalize_mac(discovery_info.macaddress),
            hostname=discovery_info.hostname,
        )
        return await self._async_handle_discovery()

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle discovery."""
        self._discovered_device = Device30303(
            ipaddress=discovery_info["ipaddress"],
            name=discovery_info["name"],
            mac=discovery_info["mac"],
            hostname=discovery_info["hostname"],
        )
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self) -> FlowResult:
        """Handle any discovery."""
        device = self._discovered_device
        assert device is not None
        mac_address = device.mac
        mac = dr.format_mac(mac_address)
        host = device.ipaddress
        await self.async_set_unique_id(mac)
        for entry in self._async_current_entries(include_ignore=False):
            if entry.unique_id == mac or entry.data[CONF_HOST] == host:
                if async_update_entry_from_discovery(self.hass, entry, device):
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )
                return self.async_abort(reason="already_configured")
        self.context[CONF_HOST] = host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == host:
                return self.async_abort(reason="already_in_progress")
        if not device.name:
            discovery = await async_discover_device(self.hass, device.ipaddress)
            if not discovery:
                return self.async_abort(reason="cannot_connect")
            self._discovered_device = discovery
        assert self._discovered_device is not None
        hostname = self._discovered_device.hostname
        if not hostname.startswith(
            MODEL_450_HOSTNAME_PREFIX
        ) and not hostname.startswith(MODEL_550_HOSTNAME_PREFIX):
            return self.async_abort(reason="not_steamist_device")
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        device = self._discovered_device
        if user_input is not None:
            return self._async_create_entry_from_device(self._discovered_device)
        self._set_confirm_only()
        placeholders = {
            "name": device.name,
            "ipaddress": device.ipaddress,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    @callback
    def _async_create_entry_from_device(self, device: Device30303) -> FlowResult:
        """Create a config entry from a device."""
        self._async_abort_entries_match({CONF_HOST: device.ipaddress})
        return self.async_create_entry(
            title=device.name,
            data={CONF_HOST: device.ipaddress, CONF_NAME: device.name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                await Steamist(
                    user_input[CONF_HOST],
                    async_get_clientsession(self.hass),
                ).async_get_status()
            except CONNECTION_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if discovery := await async_discover_device(
                    self.hass, user_input[CONF_HOST]
                ):
                    return self._async_create_entry_from_device(discovery)
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
