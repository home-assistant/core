"""Adds config flow for dnsip integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_HOSTNAME,
    CONF_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DEFAULT_HOSTNAME,
    DEFAULT_IPV6,
    DEFAULT_NAME,
    DEFAULT_RESOLVER,
    DEFAULT_RESOLVER_IPV6,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOSTNAME, default=DEFAULT_HOSTNAME): cv.string,
        vol.Optional(CONF_RESOLVER, default=DEFAULT_RESOLVER): cv.string,
        vol.Optional(CONF_IPV6, default=DEFAULT_IPV6): cv.boolean,
        vol.Optional(CONF_RESOLVER_IPV6, default=DEFAULT_RESOLVER_IPV6): cv.string,
    }
)


class DnsIPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dnsip integration."""

    VERSION = 1

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a configuration from config.yaml."""

        self.context.update({"title_placeholders": {"DNS IP": f"YAML import {DOMAIN}"}})

        hostname = config.get(CONF_HOSTNAME, DEFAULT_HOSTNAME)
        self._async_abort_entries_match({CONF_HOSTNAME: hostname})
        return await self.async_step_user(user_input=config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if user_input is not None:

            hostname = user_input.get(CONF_HOSTNAME, DEFAULT_HOSTNAME)
            name = DEFAULT_NAME if hostname == DEFAULT_HOSTNAME else hostname
            resolver = user_input.get(CONF_RESOLVER, DEFAULT_RESOLVER)
            ipv6 = user_input.get(CONF_IPV6, DEFAULT_IPV6)
            resolver_ipv6 = user_input.get(CONF_RESOLVER_IPV6, DEFAULT_RESOLVER_IPV6)

            return self.async_create_entry(
                title=name,
                data={
                    CONF_HOSTNAME: hostname,
                    CONF_NAME: name,
                    CONF_RESOLVER: resolver,
                    CONF_IPV6: ipv6,
                    CONF_RESOLVER_IPV6: resolver_ipv6,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors={},
        )
