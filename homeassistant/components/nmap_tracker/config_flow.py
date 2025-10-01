"""Config flow for Nmap Tracker integration."""

from __future__ import annotations

from ipaddress import ip_address, ip_network, summarize_address_range
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import network
from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    CONF_SCAN_INTERVAL,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.components.network import MDNS_TARGET_IP
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_HOME_INTERVAL,
    CONF_MAC_EXCLUDE,
    CONF_OPTIONS,
    DEFAULT_OPTIONS,
    DOMAIN,
    TRACKER_SCAN_INTERVAL,
)

MAX_SCAN_INTERVAL = 3600
MAX_CONSIDER_HOME = MAX_SCAN_INTERVAL * 6
DEFAULT_NETWORK_PREFIX = 24


async def async_get_network(hass: HomeAssistant) -> str:
    """Search adapters for the network."""
    # We want the local ip that is most likely to be
    # on the LAN and not the WAN so we use MDNS_TARGET_IP
    local_ip = await network.async_get_source_ip(hass, MDNS_TARGET_IP)
    network_prefix = DEFAULT_NETWORK_PREFIX
    for adapter in await network.async_get_adapters(hass):
        for ipv4 in adapter["ipv4"]:
            if ipv4["address"] == local_ip:
                network_prefix = ipv4["network_prefix"]
                break
    return str(ip_network(f"{local_ip}/{network_prefix}", False))


def _normalize_ips_and_network(hosts: str) -> list[str] | None:
    """Check if a list of hosts are all ips or ip networks."""
    normalized_hosts = []

    for host in sorted(hosts):
        try:
            start, end = host.split("-", 1)
            if "." not in end:
                ip_1, ip_2, ip_3, _ = start.split(".", 3)
                end = f"{ip_1}.{ip_2}.{ip_3}.{end}"
            summarize_address_range(ip_address(start), ip_address(end))
        except ValueError:
            pass
        else:
            normalized_hosts.append(host)
            continue

        try:
            normalized_hosts.append(str(ip_address(host)))
        except ValueError:
            pass
        else:
            continue

        try:
            normalized_hosts.append(str(ip_network(host)))
        except ValueError:
            return None

    return normalized_hosts


def _is_valid_mac(mac_address: str) -> bool:
    """Check if a mac address is valid."""
    is_valid_mac = re.match(r"([0-9A-F]{12})", string=mac_address, flags=re.IGNORECASE)
    if is_valid_mac is not None and is_valid_mac.group() is not None:
        return True
    return False


def _normalize_mac_addresses(mac_addresses: str) -> list[str] | None:
    """Check if a list of mac addresses are all valid."""
    normalized_mac_addresses = []

    for mac_address in sorted(mac_addresses):
        mac_address = mac_address.replace(":", "").replace("-", "").upper().strip()
        if not _is_valid_mac(mac_address):
            return None

        formatted_mac_address = format_mac(mac_address)
        normalized_mac_addresses.append(formatted_mac_address)

    return normalized_mac_addresses


def normalize_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate hosts and exclude are valid."""
    errors = {}
    normalized_hosts = _normalize_ips_and_network(user_input[CONF_HOSTS])
    if not normalized_hosts:
        errors[CONF_HOSTS] = "invalid_hosts"
    else:
        user_input[CONF_HOSTS] = normalized_hosts

    normalized_exclude = _normalize_ips_and_network(user_input[CONF_EXCLUDE])
    if normalized_exclude is None:
        errors[CONF_EXCLUDE] = "invalid_hosts"
    else:
        user_input[CONF_EXCLUDE] = normalized_exclude

    normalized_mac_exclude = _normalize_mac_addresses(user_input[CONF_MAC_EXCLUDE])
    if normalized_mac_exclude is None:
        errors[CONF_MAC_EXCLUDE] = "invalid_hosts"
    else:
        user_input[CONF_MAC_EXCLUDE] = normalized_mac_exclude

    return errors


async def _async_build_schema_with_user_input(
    hass: HomeAssistant, user_input: dict[str, Any], include_options: bool
) -> vol.Schema:
    hosts = user_input.get(CONF_HOSTS, [await async_get_network(hass)])
    ip_exclude = user_input.get(
        CONF_EXCLUDE, [await network.async_get_source_ip(hass, MDNS_TARGET_IP)]
    )

    mac_exclude = user_input.get(CONF_MAC_EXCLUDE, [])

    schema: VolDictType = {
        vol.Required(CONF_HOSTS, default=hosts): TextSelector(
            TextSelectorConfig(multiple=True)
        ),
        vol.Required(
            CONF_HOME_INTERVAL, default=user_input.get(CONF_HOME_INTERVAL, 0)
        ): int,
        vol.Optional(CONF_EXCLUDE, default=ip_exclude): TextSelector(
            TextSelectorConfig(multiple=True)
        ),
        vol.Optional(CONF_MAC_EXCLUDE, default=mac_exclude): TextSelector(
            TextSelectorConfig(multiple=True)
        ),
        vol.Optional(
            CONF_OPTIONS, default=user_input.get(CONF_OPTIONS, DEFAULT_OPTIONS)
        ): str,
    }
    if include_options:
        schema.update(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=user_input.get(CONF_SCAN_INTERVAL, TRACKER_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=MAX_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_CONSIDER_HOME,
                    default=user_input.get(CONF_CONSIDER_HOME)
                    or DEFAULT_CONSIDER_HOME.total_seconds(),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_CONSIDER_HOME)),
            }
        )
    return vol.Schema(schema)


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle a option flow for nmap tracker."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        errors = {}
        if user_input is not None:
            errors = normalize_input(user_input)
            self.options.update(user_input)

            if not errors:
                title_hosts = ", ".join(self.options[CONF_HOSTS])
                return self.async_create_entry(
                    title=f"Nmap Tracker {title_hosts}", data=self.options
                )

        return self.async_show_form(
            step_id="init",
            data_schema=await _async_build_schema_with_user_input(
                self.hass, self.options, True
            ),
            errors=errors,
        )


class NmapTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nmap Tracker."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize config flow."""
        self.options: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if not self._async_is_unique_host_list(user_input):
                return self.async_abort(reason="already_configured")

            errors = normalize_input(user_input)
            self.options.update(user_input)

            if not errors:
                title_hosts = ", ".join(user_input[CONF_HOSTS])
                return self.async_create_entry(
                    title=f"Nmap Tracker {title_hosts}",
                    data={},
                    options=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=await _async_build_schema_with_user_input(
                self.hass, self.options, False
            ),
            errors=errors,
        )

    def _async_is_unique_host_list(self, user_input: dict[str, Any]) -> bool:
        hosts = _normalize_ips_and_network(user_input[CONF_HOSTS])
        for entry in self._async_current_entries():
            if _normalize_ips_and_network(entry.options[CONF_HOSTS]) == hosts:
                return False
        return True

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)
