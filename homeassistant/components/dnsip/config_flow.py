"""Adds config flow for dnsip integration."""
from __future__ import annotations

from typing import Any

import aiodns
from aiodns.error import DNSError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_HOSTNAME,
    CONF_IPV4,
    CONF_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DEFAULT_HOSTNAME,
    DEFAULT_NAME,
    DEFAULT_RESOLVER,
    DEFAULT_RESOLVER_IPV6,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOSTNAME, default=DEFAULT_HOSTNAME): cv.string,
    }
)


async def async_validate_url(
    url: str, resolver_ipv4: str, resolver_ipv6: str, entry_data: dict[str, Any]
) -> dict[str, bool]:
    """Validate url."""
    result = {}
    ipv4 = None
    ipv6 = None
    if entry_data[CONF_IPV4]:
        try:
            ipv4 = await aiodns.DNSResolver(nameservers=[resolver_ipv4]).query(url, "A")
        except DNSError:
            ipv4 = None
    if entry_data[CONF_IPV6]:
        try:
            ipv6 = await aiodns.DNSResolver(nameservers=[resolver_ipv6]).query(
                url, "AAAA"
            )
        except DNSError:
            ipv6 = None

    result[CONF_IPV4] = bool(ipv4)
    result[CONF_IPV6] = bool(ipv6)

    return result


class DnsIPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dnsip integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> DnsIPOptionsFlowHandler:
        """Return Option handler."""
        return DnsIPOptionsFlowHandler(config_entry)

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a configuration from config.yaml."""

        hostname = config.get(CONF_HOSTNAME, DEFAULT_HOSTNAME)
        self._async_abort_entries_match({CONF_HOSTNAME: hostname})
        config[CONF_HOSTNAME] = hostname
        return await self.async_step_user(user_input=config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input:

            hostname = user_input[CONF_HOSTNAME]
            name = DEFAULT_NAME if hostname == DEFAULT_HOSTNAME else hostname
            resolver = DEFAULT_RESOLVER
            resolver_ipv6 = DEFAULT_RESOLVER_IPV6

            validate = await async_validate_url(
                hostname, resolver, resolver_ipv6, {CONF_IPV4: True, CONF_IPV6: True}
            )

            if not validate[CONF_IPV4] and not validate[CONF_IPV6]:
                errors["base"] = "invalid_hostname"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOSTNAME: hostname,
                        CONF_NAME: name,
                        CONF_RESOLVER: resolver,
                        CONF_RESOLVER_IPV6: resolver_ipv6,
                        CONF_IPV4: validate[CONF_IPV4],
                        CONF_IPV6: validate[CONF_IPV6],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class DnsIPOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option config flow for dnsip integration."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}
        if user_input is not None:
            validate = await async_validate_url(
                self.entry.data[CONF_HOSTNAME],
                user_input[CONF_RESOLVER],
                user_input[CONF_RESOLVER_IPV6],
                {
                    CONF_IPV4: self.entry.data[CONF_IPV4],
                    CONF_IPV6: self.entry.data[CONF_IPV6],
                },
            )
            if validate[CONF_IPV4] is False and self.entry.data[CONF_IPV4] is True:
                errors[CONF_RESOLVER] = "invalid_resolver"
            elif validate[CONF_IPV6] is False and self.entry.data[CONF_IPV6] is True:
                errors[CONF_RESOLVER_IPV6] = "invalid_resolver"
            else:
                return self.async_create_entry(title=self.entry.title, data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_RESOLVER,
                        default=self.entry.options.get(CONF_RESOLVER, DEFAULT_RESOLVER),
                    ): cv.string,
                    vol.Optional(
                        CONF_RESOLVER_IPV6,
                        default=self.entry.options.get(
                            CONF_RESOLVER_IPV6, DEFAULT_RESOLVER_IPV6
                        ),
                    ): cv.string,
                }
            ),
            errors=errors,
        )
