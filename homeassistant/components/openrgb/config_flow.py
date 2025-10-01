"""Config flow for the OpenRGB integration."""

from __future__ import annotations

from functools import partial
from ipaddress import IPv6Address, ip_address
import logging
from typing import Any

from getmac import get_mac_address
from openrgb import OpenRGBClient
from openrgb.utils import OpenRGBDisconnected, SDKVersionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DEFAULT_CLIENT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, host: str, port: int) -> None:
    """Validate the user input allows us to connect."""
    client = await hass.async_add_executor_job(
        OpenRGBClient, host, port, DEFAULT_CLIENT_NAME
    )
    await hass.async_add_executor_job(client.disconnect)


# Modified from dlna_dmr
async def _async_get_mac(hass: HomeAssistant, host: str) -> str | None:
    """Get MAC address from host name, IPv4 address, or IPv6 address."""
    # getmac has trouble using IPv6 addresses as the "hostname" parameter so
    # assume host is an IP address, then handle the case it's not.
    try:
        ip_addr = ip_address(host)
    except ValueError:
        mac = await hass.async_add_executor_job(partial(get_mac_address, hostname=host))
    else:
        if ip_addr.version == 4:
            mac = await hass.async_add_executor_job(partial(get_mac_address, ip=host))
        else:
            # Drop scope_id from IPv6 address by converting via int
            ip_addr = IPv6Address(int(ip_addr))
            mac = await hass.async_add_executor_job(
                partial(get_mac_address, ip6=str(ip_addr))
            )

    if mac is None:
        return None

    return format_mac(mac)


class OpenRGBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenRGB."""

    VERSION = 1

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the OpenRGB SDK Server."""
        reconfigure_entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            server_slug = f"{host}:{port}"

            try:
                await validate_input(self.hass, host, port)
            except (
                ConnectionRefusedError,
                OpenRGBDisconnected,
                OSError,
                SDKVersionError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unknown error while connecting to OpenRGB SDK Server at %s",
                    server_slug,
                )
                errors["base"] = "unknown"
            else:
                # Try to get MAC address to register for DHCP discovery
                mac = await _async_get_mac(self.hass, host)

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: host, CONF_PORT: port, CONF_MAC: mac},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=reconfigure_entry.data[CONF_HOST],
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=reconfigure_entry.data[CONF_PORT],
                    ): int,
                }
            ),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP updates."""
        mac = format_mac(discovery_info.macaddress)

        for entry in self._async_current_entries():
            if entry.data[CONF_MAC] == mac:
                update_ok = self.hass.config_entries.async_update_entry(
                    entry,
                    data=entry.data | {CONF_HOST: discovery_info.ip},
                )
                if update_ok:
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="already_configured")

        return self.async_abort(reason="unknown")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            server_slug = f"{host}:{port}"

            try:
                await validate_input(self.hass, host, port)
            except (
                ConnectionRefusedError,
                OpenRGBDisconnected,
                OSError,
                SDKVersionError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unknown error while connecting to OpenRGB SDK Server at %s",
                    server_slug,
                )
                errors["base"] = "unknown"
            else:
                # Try to get MAC address to register for DHCP discovery
                mac = await _async_get_mac(self.hass, host)

                # Use MAC as unique ID if available, otherwise use host:port
                unique_id = mac or f"{host}:{port}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                if mac is None:
                    title = f"OpenRGB ({host}:{port})"
                else:
                    title = f"OpenRGB ({mac})"

                return self.async_create_entry(
                    title=title, data={CONF_HOST: host, CONF_PORT: port, CONF_MAC: mac}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )
