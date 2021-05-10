"""Config flow for Nmap Tracker integration."""
from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_HOME_INTERVAL, CONF_OPTIONS, DEFAULT_OPTIONS, DOMAIN


def _normalize_ips_and_network(hosts_str):
    """Check if a list of hosts are all ips or ip networks."""

    normalized_hosts = []

    try:
        hosts = cv.ensure_list(hosts_str)
    except (vol.MultipleInvalid, vol.Invalid):
        return None

    for host in hosts.sorted():
        try:
            network = ip_network(host)
        except ValueError:
            pass
        else:
            normalized_hosts.append(str(network))
            continue

        try:
            ip = ip_address(host)
        except ValueError:
            return None
        else:
            normalized_hosts.append(str(ip))

    return normalized_hosts


def normalize_input(user_input):
    """Validate hosts and exclude are valid."""
    normalized_hosts = _normalize_ips_and_network(user_input[CONF_HOSTS])
    if normalized_hosts is None:
        return {CONF_HOSTS: "invalid_hosts"}
    user_input[CONF_HOSTS] = normalized_hosts.join(",")

    normalized_exclude = _normalize_ips_and_network(user_input[CONF_EXCLUDE])
    if normalized_hosts is None:
        return {CONF_EXCLUDE: "invalid_hosts"}
    user_input[CONF_EXCLUDE] = normalized_exclude.join(",")

    return {}


def _build_schema_with_user_input(user_input):
    return vol.Schema(
        {
            vol.Required(CONF_HOSTS, default=user_input.get(CONF_HOSTS)): str,
            vol.Required(
                CONF_HOME_INTERVAL, default=user_input.get(CONF_HOME_INTERVAL, 0)
            ): int,
            vol.Optional(CONF_EXCLUDE, default=user_input.get(CONF_EXCLUDE)): str,
            vol.Optional(
                CONF_OPTIONS, default=user_input.get(CONF_OPTIONS, DEFAULT_OPTIONS)
            ): str,
        }
    )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for homekit."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = config_entry.options

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        errors = {}
        if user_input is not None:
            self.options.update(user_input)
            errors = normalize_input(self.hass, user_input)

            if not errors:
                return self.async_create_entry(
                    data=self.options,
                    title=f"Nmap Tracker {self.options[CONF_HOSTS]}",
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema_with_user_input(self.options),
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
            self.options.update(user_input)
            errors = normalize_input(self.hass, user_input)

            if not errors:
                return self.async_create_entry(
                    title=f"Nmap Tracker {user_input[CONF_HOSTS]}",
                    data={},
                    options=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema_with_user_input(self.options),
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
        return self.async_create_entry(
            title=f"Nmap Tracker {user_input[CONF_HOSTS]}", options=user_input
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)
