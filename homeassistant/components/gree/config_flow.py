"""Config flow for Gree."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

from greeclimate.device import Device, DeviceInfo
from greeclimate.discovery import Discovery
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
import voluptuous as vol

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS

from .const import DEFAULT_PORT, DISCOVERY_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _validate_ip_address(value: str) -> str:
    """Validate that value is a valid IP address."""
    try:
        ipaddress.ip_address(value)
    except ValueError as err:
        raise vol.Invalid("Not a valid IP address") from err
    return value


MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): vol.All(str, _validate_ip_address),
    }
)


class GreeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gree Climate."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["scan", "manual"],
        )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle network scan step."""
        if user_input is None:
            return self.async_show_form(step_id="scan")

        # Abort if a discovery-mode entry (without a static IP) already exists
        if any(
            CONF_IP_ADDRESS not in entry.data
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="single_instance_allowed")

        gree_discovery = Discovery(DISCOVERY_TIMEOUT)
        bcast_addr = list(await async_get_ipv4_broadcast_addresses(self.hass))
        devices = await gree_discovery.scan(
            wait_for=DISCOVERY_TIMEOUT, bcast_ifaces=bcast_addr
        )
        if not devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_create_entry(title="Gree Climate", data={})

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP entry step."""
        # Abort if a discovery-mode entry exists; manual entries would create
        # duplicate entities for devices already managed by discovery.
        for entry in self._async_current_entries():
            if CONF_IP_ADDRESS not in entry.data:
                return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            ip_address = user_input[CONF_IP_ADDRESS]
            device_info = DeviceInfo(ip_address, DEFAULT_PORT, "", "")
            device = Device(device_info)

            try:
                await device.bind()
            except (DeviceNotBoundError, DeviceTimeoutError) as err:
                _LOGGER.debug(
                    "Failed to connect to Gree device at %s: %s", ip_address, err
                )
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error connecting to Gree device at %s", ip_address
                )
                errors["base"] = "cannot_connect"
            else:
                mac = device.device_info.mac
                if mac:
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured()

                title = device.device_info.name or ip_address
                return self.async_create_entry(
                    title=title,
                    data={CONF_IP_ADDRESS: ip_address},
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=MANUAL_SCHEMA,
            errors=errors,
        )
