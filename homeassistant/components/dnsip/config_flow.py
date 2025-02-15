"""Adds config flow for dnsip integration."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import aiodns
from aiodns.error import DNSError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_HOSTNAME,
    CONF_IPV4,
    CONF_IPV6,
    CONF_IPV6_V4,
    CONF_PORT_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DEFAULT_HOSTNAME,
    DEFAULT_NAME,
    DEFAULT_PORT,
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
        vol.Optional(CONF_RESOLVER): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_RESOLVER_IPV6): cv.string,
        vol.Optional(CONF_PORT_IPV6): cv.port,
    }
)


async def async_validate_hostname(
    hostname: str,
    resolver_ipv4: str,
    resolver_ipv6: str,
    port: int,
    port_ipv6: int,
) -> dict[str, bool]:
    """Validate hostname."""

    async def async_check(
        hostname: str, resolver: str, qtype: str, port: int = 53
    ) -> bool:
        """Return if able to resolve hostname."""
        result = False
        with contextlib.suppress(DNSError):
            result = bool(
                await aiodns.DNSResolver(
                    nameservers=[resolver], udp_port=port, tcp_port=port
                ).query(hostname, qtype)
            )
        return result

    result: dict[str, bool] = {}

    tasks = await asyncio.gather(
        async_check(hostname, resolver_ipv4, "A", port=port),
        async_check(hostname, resolver_ipv6, "AAAA", port=port_ipv6),
        async_check(hostname, resolver_ipv4, "AAAA", port=port),
    )

    result[CONF_IPV4] = tasks[0]
    result[CONF_IPV6] = tasks[1]
    result[CONF_IPV6_V4] = tasks[2]

    return result


class DnsIPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dnsip integration."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> DnsIPOptionsFlowHandler:
        """Return Option handler."""
        return DnsIPOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input:
            hostname = user_input[CONF_HOSTNAME]
            name = DEFAULT_NAME if hostname == DEFAULT_HOSTNAME else hostname
            resolver = user_input.get(CONF_RESOLVER, DEFAULT_RESOLVER)
            resolver_ipv6 = user_input.get(CONF_RESOLVER_IPV6, DEFAULT_RESOLVER_IPV6)
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            port_ipv6 = user_input.get(CONF_PORT_IPV6, DEFAULT_PORT)

            validate = await async_validate_hostname(
                hostname, resolver, resolver_ipv6, port, port_ipv6
            )

            set_resolver = resolver
            if validate[CONF_IPV6]:
                set_resolver = resolver_ipv6

            if (
                not validate[CONF_IPV4]
                and not validate[CONF_IPV6]
                and not validate[CONF_IPV6_V4]
            ):
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
                        CONF_IPV6: validate[CONF_IPV6] or validate[CONF_IPV6_V4],
                    },
                    options={
                        CONF_RESOLVER: resolver,
                        CONF_PORT: port,
                        CONF_RESOLVER_IPV6: set_resolver,
                        CONF_PORT_IPV6: port_ipv6,
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


class DnsIPOptionsFlowHandler(OptionsFlow):
    """Handle a option config flow for dnsip integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}
        if user_input is not None:
            resolver = user_input.get(CONF_RESOLVER, DEFAULT_RESOLVER)
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            resolver_ipv6 = user_input.get(CONF_RESOLVER_IPV6, DEFAULT_RESOLVER_IPV6)
            port_ipv6 = user_input.get(CONF_PORT_IPV6, DEFAULT_PORT)
            validate = await async_validate_hostname(
                self.config_entry.data[CONF_HOSTNAME],
                resolver,
                resolver_ipv6,
                port,
                port_ipv6,
            )

            if (
                validate[CONF_IPV4] is False
                and self.config_entry.data[CONF_IPV4] is True
            ):
                errors[CONF_RESOLVER] = "invalid_resolver"
            elif (
                validate[CONF_IPV6] is False
                and self.config_entry.data[CONF_IPV6] is True
            ):
                errors[CONF_RESOLVER_IPV6] = "invalid_resolver"
            else:
                return self.async_create_entry(
                    title=self.config_entry.title,
                    data={
                        CONF_RESOLVER: resolver,
                        CONF_PORT: port,
                        CONF_RESOLVER_IPV6: resolver_ipv6,
                        CONF_PORT_IPV6: port_ipv6,
                    },
                )

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Optional(CONF_RESOLVER): cv.string,
                    vol.Optional(CONF_PORT): cv.port,
                    vol.Optional(CONF_RESOLVER_IPV6): cv.string,
                    vol.Optional(CONF_PORT_IPV6): cv.port,
                }
            ),
            self.config_entry.options,
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
