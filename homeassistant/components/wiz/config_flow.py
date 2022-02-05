"""Config flow for WiZ Platform."""
from __future__ import annotations

import logging
from typing import Any

from pywizlight import wizlight
from pywizlight.discovery import DiscoveredBulb
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, WIZ_EXCEPTIONS
from .utils import name_from_bulb_type_and_mac

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiZ."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: DiscoveredBulb | None = None
        self._name: str | None = None

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        self._discovered_device = DiscoveredBulb(
            discovery_info.ip, discovery_info.macaddress
        )
        return await self._async_handle_discovery()

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, str]
    ) -> FlowResult:
        """Handle integration discovery."""
        self._discovered_device = DiscoveredBulb(
            discovery_info["ip_address"], discovery_info["mac_address"]
        )
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self) -> FlowResult:
        """Handle any discovery."""
        device = self._discovered_device
        assert device is not None
        _LOGGER.debug("Discovered device: %s", device)
        ip_address = device.ip_address
        mac = device.mac_address
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: ip_address})
        bulb = wizlight(ip_address)
        try:
            bulbtype = await bulb.get_bulbtype()
        except WIZ_EXCEPTIONS:
            return self.async_abort(reason="cannot_connect")
        self._name = name_from_bulb_type_and_mac(bulbtype, mac)
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        assert self._name is not None
        ip_address = self._discovered_device.ip_address
        if user_input is not None:
            return self.async_create_entry(
                title=self._name,
                data={CONF_HOST: ip_address},
            )

        self._set_confirm_only()
        placeholders = {"name": self._name, "host": ip_address}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=placeholders,
            data_schema=vol.Schema({}),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            bulb = wizlight(user_input[CONF_HOST])
            try:
                mac = await bulb.getMac()
                bulbtype = await bulb.get_bulbtype()
            except WizLightTimeOutError:
                errors["base"] = "bulb_time_out"
            except ConnectionRefusedError:
                errors["base"] = "cannot_connect"
            except WizLightConnectionError:
                errors["base"] = "no_wiz_light"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(mac, raise_on_progress=False)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                name = name_from_bulb_type_and_mac(bulbtype, mac)
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
