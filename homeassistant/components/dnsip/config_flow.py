"""Adds config flow for dnsip integration."""
from __future__ import annotations

import asyncio
import contextlib
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
DATA_SCHEMA_ADV = vol.Schema(
    {
        vol.Required(CONF_HOSTNAME, default=DEFAULT_HOSTNAME): cv.string,
        vol.Optional(CONF_RESOLVER, default=DEFAULT_RESOLVER): cv.string,
        vol.Optional(CONF_RESOLVER_IPV6, default=DEFAULT_RESOLVER_IPV6): cv.string,
    }
)


async def async_validate_hostname(
    hostname: str, resolver_ipv4: str, resolver_ipv6: str
) -> dict[str, bool]:
    """Validate hostname."""

    async def async_check(hostname: str, resolver: str, qtype: str) -> bool:
        """Return if able to resolve hostname."""
        result = False
        with contextlib.suppress(DNSError):
            result = bool(
                await aiodns.DNSResolver(nameservers=[resolver]).query(hostname, qtype)
            )
        return result

    result: dict[str, bool] = {}

    tasks = await asyncio.gather(
        async_check(hostname, resolver_ipv4, "A"),
        async_check(hostname, resolver_ipv6, "AAAA"),
    )

    result[CONF_IPV4] = tasks[0]
    result[CONF_IPV6] = tasks[1]

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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input:

            hostname = user_input[CONF_HOSTNAME]
            name = DEFAULT_NAME if hostname == DEFAULT_HOSTNAME else hostname
            resolver = user_input.get(CONF_RESOLVER, DEFAULT_RESOLVER)
            resolver_ipv6 = user_input.get(CONF_RESOLVER_IPV6, DEFAULT_RESOLVER_IPV6)

            validate = await async_validate_hostname(hostname, resolver, resolver_ipv6)

            if not validate[CONF_IPV4] and not validate[CONF_IPV6]:
                errors["base"] = "invalid_hostname"
            else:
                await self.async_set_unique_id(hostname)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOSTNAME: hostname,
                        CONF_NAME: name,
                        CONF_IPV4: validate[CONF_IPV4],
                        CONF_IPV6: validate[CONF_IPV6],
                    },
                    options={
                        CONF_RESOLVER: resolver,
                        CONF_RESOLVER_IPV6: resolver_ipv6,
                    },
                )

        if self.show_advanced_options is True:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA_ADV,
                errors=errors,
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
            validate = await async_validate_hostname(
                self.entry.data[CONF_HOSTNAME],
                user_input[CONF_RESOLVER],
                user_input[CONF_RESOLVER_IPV6],
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
