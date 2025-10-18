"""Config flow for the OpenRGB integration."""

from __future__ import annotations

from functools import partial
from ipaddress import IPv6Address, ip_address
import logging
from typing import Any

from getmac import get_mac_address
from openrgb import OpenRGBClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONNECTION_ERRORS, DEFAULT_CLIENT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def validate_input(hass: HomeAssistant, host: str, port: int) -> None:
    """Validate the user input allows us to connect."""

    def _try_connect(host: str, port: int) -> None:
        client = OpenRGBClient(host, port, DEFAULT_CLIENT_NAME)
        client.disconnect()

    await hass.async_add_executor_job(_try_connect, host, port)


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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the OpenRGB SDK Server."""
        reconfigure_entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Prevent duplicate entries
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            try:
                await validate_input(self.hass, host, port)
            except CONNECTION_ERRORS:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unknown error while connecting to OpenRGB SDK server at %s",
                    f"{host}:{port}",
                )
                errors["base"] = "unknown"
            else:
                # Try to get MAC address to register for IP updates via DHCP discovery
                mac = await _async_get_mac(self.hass, host)

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: host, CONF_PORT: port, CONF_MAC: mac},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_RECONFIGURE_DATA_SCHEMA,
                suggested_values={
                    CONF_HOST: reconfigure_entry.data[CONF_HOST],
                    CONF_PORT: reconfigure_entry.data[CONF_PORT],
                },
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
                await self.async_set_unique_id(entry.entry_id)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: discovery_info.ip},
                    reload_on_update=True,
                )

        return self.async_abort(reason="unknown")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME]
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Prevent duplicate entries
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            try:
                await validate_input(self.hass, host, port)
            except CONNECTION_ERRORS:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unknown error while connecting to OpenRGB SDK server at %s",
                    f"{host}:{port}",
                )
                errors["base"] = "unknown"
            else:
                # Try to get MAC address to register for IP updates via DHCP discovery
                mac = await _async_get_mac(self.hass, host)

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_MAC: mac,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )
