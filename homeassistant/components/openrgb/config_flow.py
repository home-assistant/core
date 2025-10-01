"""Config flow for the OpenRGB integration."""

from __future__ import annotations

from functools import partial
from ipaddress import IPv6Address, ip_address
import logging
from typing import Any

from getmac import get_mac_address
from openrgb import OpenRGBClient
from openrgb.utils import ControllerParsingError, OpenRGBDisconnected, SDKVersionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DEFAULT_CLIENT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def validate_input(hass: HomeAssistant, host: str, port: int) -> None:
    """Validate the user input allows us to connect."""
    client = await hass.async_add_executor_job(
        OpenRGBClient, host, port, DEFAULT_CLIENT_NAME
    )
    await hass.async_add_executor_job(client.disconnect)


# Taken from dlna_dmr
async def _async_get_mac_address(hass: HomeAssistant, host: str) -> str:
    """Get mac address from host name, IPv4 address, or IPv6 address."""
    # Help mypy, which has trouble with the async_add_executor_job + partial call
    mac_address: str | None
    # getmac has trouble using IPv6 addresses as the "hostname" parameter so
    # assume host is an IP address, then handle the case it's not.
    try:
        ip_addr = ip_address(host)
    except ValueError:
        mac_address = await hass.async_add_executor_job(
            partial(get_mac_address, hostname=host)
        )
    else:
        if ip_addr.version == 4:
            mac_address = await hass.async_add_executor_job(
                partial(get_mac_address, ip=host)
            )
        else:
            # Drop scope_id from IPv6 address by converting via int
            ip_addr = IPv6Address(int(ip_addr))
            mac_address = await hass.async_add_executor_job(
                partial(get_mac_address, ip6=str(ip_addr))
            )

    if mac_address is None:
        raise UnableToDetermineMac

    return format_mac(mac_address)


class OpenRGBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenRGB."""

    VERSION = 1

    _reconfigure_entry: ConfigEntry | None = None

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
                mac = await _async_get_mac_address(self.hass, host)
            except ValueError:
                errors["base"] = "invalid_host"
            except UnableToDetermineMac:
                errors["base"] = "unable_to_determine_mac"
            else:
                try:
                    await validate_input(self.hass, host, port)
                except (
                    ConnectionRefusedError,
                    OpenRGBDisconnected,
                    SDKVersionError,
                    ControllerParsingError,
                ):
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception(
                        "Unknown error while connecting to OpenRGB SDK Server at %s",
                        server_slug,
                    )
                    errors["base"] = "unknown"
                else:
                    old_mac = reconfigure_entry.data[CONF_MAC]
                    existing_entry = await self.async_set_unique_id(mac)

                    if (
                        existing_entry is not None
                        and existing_entry.entry_id != reconfigure_entry.entry_id
                    ):
                        self._abort_if_unique_id_mismatch(
                            reason="device_already_registered"
                        )

                    # If MAC address changed, trigger entity/device migration
                    data_updates = {CONF_HOST: host, CONF_PORT: port, CONF_MAC: mac}
                    if old_mac != mac:
                        data_updates["_migrate_mac"] = {"old": old_mac, "new": mac}

                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data_updates=data_updates,
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
        """Handle DHCP discovery."""
        mac = format_mac(discovery_info.macaddress)

        for entry in self._async_current_entries():
            if entry.data[CONF_MAC] == mac:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=entry.data | {CONF_HOST: discovery_info.ip},
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
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
                mac = await _async_get_mac_address(self.hass, host)
            except ValueError:
                errors["base"] = "invalid_host"
            except UnableToDetermineMac:
                errors["base"] = "unable_to_determine_mac"
            else:
                try:
                    await validate_input(self.hass, host, port)
                except (
                    ConnectionRefusedError,
                    OpenRGBDisconnected,
                    SDKVersionError,
                    ControllerParsingError,
                ):
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception(
                        "Unknown error while connecting to OpenRGB SDK Server at %s",
                        server_slug,
                    )
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"OpenRGB ({mac})",
                        data={CONF_HOST: host, CONF_PORT: port, CONF_MAC: mac},
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class UnableToDetermineMac(HomeAssistantError):
    """Error to indicate it is unable to determine MAC address for a given host."""
