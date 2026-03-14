"""Config flow for the power_hub integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_test_port(port: int) -> None:
    """Verify the UDP port can be bound.

    Raises OSError if the port is unavailable (e.g. already in use).
    """
    loop = asyncio.get_event_loop()
    transport, _ = await loop.create_datagram_endpoint(
        asyncio.DatagramProtocol,
        local_addr=("0.0.0.0", port),
        reuse_port=True,
    )
    transport.close()


class BitvisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bitvis Power Hub."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: zeroconf.ZeroconfServiceInfo | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            try:
                await _async_test_port(port)
            except OSError:
                errors["base"] = "cannot_connect"
            else:
                # Create unique ID based on host
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Discovered Bitvis Power Hub via Zeroconf: %s", discovery_info)

        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT

        # Set unique ID to prevent duplicates
        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        # Show confirmation to user
        self.context["title_placeholders"] = {
            "name": discovery_info.name or DEFAULT_NAME,
            "host": host,
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            assert self._discovery_info is not None
            host = self._discovery_info.host
            port = self._discovery_info.port or DEFAULT_PORT

            try:
                await _async_test_port(port)
            except OSError:
                return self.async_abort(reason="cannot_connect")

            return self.async_create_entry(
                title=self._discovery_info.name or DEFAULT_NAME,
                data={
                    CONF_HOST: host,
                    CONF_PORT: port,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._discovery_info.name
                if self._discovery_info
                else DEFAULT_NAME,
                "host": self._discovery_info.host if self._discovery_info else "",
            },
        )
