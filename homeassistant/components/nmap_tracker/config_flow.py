"""Config flow for Nmap Tracker integration."""
from __future__ import annotations

from ipaddress import ip_address, ip_network, summarize_address_range
from typing import Any

import ifaddr
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.util import get_local_ip

from .const import CONF_HOME_INTERVAL, CONF_OPTIONS, DEFAULT_OPTIONS, DOMAIN

DEFAULT_NETWORK_PREFIX = 24


def get_network():
    """Search adapters for the network."""
    adapters = ifaddr.get_adapters()
    local_ip = get_local_ip()
    network_prefix = (
        get_ip_prefix_from_adapters(local_ip, adapters) or DEFAULT_NETWORK_PREFIX
    )
    return str(ip_network(f"{local_ip}/{network_prefix}", False))


def get_ip_prefix_from_adapters(local_ip, adapters):
    """Find the network prefix for an adapter."""
    for adapter in adapters:
        for ip_cfg in adapter.ips:
            if local_ip == ip_cfg.ip:
                return ip_cfg.network_prefix


def _normalize_ips_and_network(hosts_str):
    """Check if a list of hosts are all ips or ip networks."""

    normalized_hosts = []
    hosts = [host for host in cv.ensure_list_csv(hosts_str) if host != ""]

    for host in sorted(hosts):
        try:
            start, end = host.split("-", 1)
            if "." not in end:
                ip_1, ip_2, ip_3, _ = start.split(".", 3)
                end = ".".join([ip_1, ip_2, ip_3, end])
            summarize_address_range(ip_address(start), ip_address(end))
        except ValueError:
            pass
        else:
            normalized_hosts.append(host)
            continue

        try:
            ip_addr = ip_address(host)
        except ValueError:
            pass
        else:
            normalized_hosts.append(str(ip_addr))
            continue

        try:
            network = ip_network(host)
        except ValueError:
            return None
        else:
            normalized_hosts.append(str(network))

    return normalized_hosts


def normalize_input(user_input):
    """Validate hosts and exclude are valid."""
    errors = {}
    normalized_hosts = _normalize_ips_and_network(user_input[CONF_HOSTS])
    if not normalized_hosts:
        errors[CONF_HOSTS] = "invalid_hosts"
    else:
        user_input[CONF_HOSTS] = ",".join(normalized_hosts)

    normalized_exclude = _normalize_ips_and_network(user_input[CONF_EXCLUDE])
    if normalized_exclude is None:
        errors[CONF_EXCLUDE] = "invalid_hosts"
    else:
        user_input[CONF_EXCLUDE] = ",".join(normalized_exclude)

    return errors


async def _async_build_schema_with_user_input(hass, user_input):
    hosts = user_input.get(CONF_HOSTS, await hass.async_add_executor_job(get_network))
    exclude = user_input.get(
        CONF_EXCLUDE, await hass.async_add_executor_job(get_local_ip)
    )
    return vol.Schema(
        {
            vol.Required(CONF_HOSTS, default=hosts): str,
            vol.Required(
                CONF_HOME_INTERVAL, default=user_input.get(CONF_HOME_INTERVAL, 0)
            ): int,
            vol.Optional(CONF_EXCLUDE, default=exclude): str,
            vol.Optional(
                CONF_OPTIONS, default=user_input.get(CONF_OPTIONS, DEFAULT_OPTIONS)
            ): str,
        }
    )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for homekit."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        errors = {}
        if user_input is not None:
            errors = normalize_input(user_input)
            self.options.update(user_input)

            if not errors:
                return self.async_create_entry(
                    title=f"Nmap Tracker {self.options[CONF_HOSTS]}", data=self.options
                )

        return self.async_show_form(
            step_id="init",
            data_schema=await _async_build_schema_with_user_input(
                self.hass, self.options
            ),
            errors=errors,
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nmap Tracker."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self.options = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if not self._async_is_unique_host_list(user_input):
                return self.async_abort(reason="already_configured")

            errors = normalize_input(user_input)
            self.options.update(user_input)

            if not errors:
                return self.async_create_entry(
                    title=f"Nmap Tracker {user_input[CONF_HOSTS]}",
                    data={},
                    options=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=await _async_build_schema_with_user_input(
                self.hass, self.options
            ),
            errors=errors,
        )

    def _async_is_unique_host_list(self, user_input):
        hosts = _normalize_ips_and_network(user_input[CONF_HOSTS])
        for entry in self._async_current_entries():
            if _normalize_ips_and_network(entry.options[CONF_HOSTS]) == hosts:
                return False
        return True

    async def async_step_import(self, user_input=None):
        """Handle import from yaml."""
        if not self._async_is_unique_host_list(user_input):
            return self.async_abort(reason="already_configured")

        normalize_input(user_input)

        return self.async_create_entry(
            title=f"Nmap Tracker {user_input[CONF_HOSTS]}", data={}, options=user_input
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)
