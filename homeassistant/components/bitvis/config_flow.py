"""Config flow for the Bitvis Power Hub integration."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

from bitvis_protobuf.utils import format_unique_id, normalize_host
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .coordinator import async_get_listener_registry

_LOGGER = logging.getLogger(__name__)


async def _async_test_port(hass: HomeAssistant, port: int) -> None:
    """Verify the UDP port can be bound.

    Skips the check when HA already owns a shared listener on this port (a
    second device on the same port is valid — it will share the existing socket).
    Raises OSError if the port is unavailable (e.g. already in use by another
    process) or invalid.
    """
    if async_get_listener_registry(hass).has_listener(port):
        return

    loop = asyncio.get_running_loop()
    transports: list[asyncio.DatagramTransport] = []
    bind_errors: list[Exception] = []
    for family, local_addr in (
        (socket.AF_INET6, ("::", port)),
        (socket.AF_INET, ("0.0.0.0", port)),
    ):
        try:
            transport, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol,
                local_addr=local_addr,
                family=family,
            )
        except (OSError, ValueError) as err:
            bind_errors.append(err)
        else:
            assert isinstance(transport, asyncio.DatagramTransport)
            transports.append(transport)

    if not transports:
        raise OSError("UDP port is unavailable or invalid") from bind_errors[0]

    for transport in transports:
        transport.close()


def _resolve_host(host: str) -> str:
    """Resolve a host to an IP address (IPv4 or IPv6)."""
    # Use AF_UNSPEC to allow both IPv4 and IPv6, and pick the first result.
    info = socket.getaddrinfo(
        host,
        None,
        family=socket.AF_UNSPEC,
        type=socket.SOCK_STREAM,
    )
    return str(info[0][4][0])


class BitvisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bitvis Power Hub."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: ZeroconfServiceInfo | None = None

    def _get_friendly_name(self, name: str | None) -> str:
        """Return a user-friendly name derived from the zeroconf name."""
        if not name:
            return DEFAULT_NAME
        instance = name.split(".", 1)[0]
        return instance or DEFAULT_NAME

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            port = user_input[CONF_PORT]

            try:
                await _async_test_port(self.hass, port)
            except OSError:
                errors["base"] = "cannot_connect"
            else:
                # Normalize the host for unique_id to match zeroconf behavior.
                try:
                    resolved_host = await self.hass.async_add_executor_job(
                        _resolve_host, host
                    )
                except socket.gaierror:
                    _LOGGER.warning(
                        "Could not resolve host %s, using it as-is for unique_id", host
                    )
                    resolved_host = host

                await self.async_set_unique_id(format_unique_id(resolved_host, port))
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
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Discovered Bitvis Power Hub via Zeroconf: %s", discovery_info)

        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT

        # Set unique ID to prevent duplicates
        await self.async_set_unique_id(format_unique_id(host, port))
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        # Show confirmation to user
        self.context["title_placeholders"] = {
            "name": self._get_friendly_name(discovery_info.name),
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
                await _async_test_port(self.hass, port)
            except OSError:
                return self.async_abort(reason="cannot_connect")

            return self.async_create_entry(
                title=self._get_friendly_name(self._discovery_info.name),
                data={
                    CONF_HOST: host,
                    CONF_PORT: port,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._get_friendly_name(
                    self._discovery_info.name if self._discovery_info else None
                ),
                "host": self._discovery_info.host if self._discovery_info else "",
            },
        )
