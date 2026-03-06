"""Config flow for Qube Heat Pump integration."""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
import socket
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

if TYPE_CHECKING:
    from collections.abc import Iterable

_LOGGER = logging.getLogger(__name__)


async def _async_resolve_host(host: str) -> str | None:
    """Resolve a host or IP string to a canonical IP address."""
    if not host:
        return None
    with contextlib.suppress(ValueError):
        return str(ipaddress.ip_address(host))

    with contextlib.suppress(OSError):
        infos = await asyncio.get_running_loop().getaddrinfo(
            host,
            None,
            type=socket.SOCK_STREAM,
        )
        for family, _, _, _, sockaddr in infos:
            if not sockaddr:
                continue
            addr = sockaddr[0]
            if not isinstance(addr, str):
                continue
            if family == socket.AF_INET6 and addr.startswith("::ffff:"):
                addr = addr.removeprefix("::ffff:")
            return addr
    return None


async def _async_find_conflicting_entry(
    entries: Iterable[config_entries.ConfigEntry],
    host: str,
) -> tuple[config_entries.ConfigEntry, str | None] | None:
    """Return a config entry that conflicts with the provided host."""
    candidate_ip = await _async_resolve_host(host)
    for entry in entries:
        existing_host = entry.data.get(CONF_HOST)
        if not existing_host:
            continue
        if existing_host == host:
            return entry, existing_host
        existing_ip = await _async_resolve_host(existing_host)
        if candidate_ip and existing_ip and existing_ip == candidate_ip:
            return entry, existing_ip
    return None


class QubeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qube Heat Pump."""

    VERSION = 1

    def _get_default_name(self) -> str:
        """Generate default device name based on existing entries."""
        existing = len(self._async_current_entries())
        return f"qube {existing + 1}"

    async def _async_has_conflicting_host(
        self, host: str, skip_entry_id: str | None = None
    ) -> bool:
        """Check if host resolves to an IP already used by another entry."""
        entries = [
            entry
            for entry in self._async_current_entries()
            if not skip_entry_id or entry.entry_id != skip_entry_id
        ]
        conflict = await _async_find_conflicting_entry(entries, host)
        if conflict:
            entry, match = conflict
            _LOGGER.debug(
                "Host %s resolves to %s already used by entry %s; blocking duplicate",
                host,
                match,
                entry.entry_id,
            )
            return True
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]
            port = DEFAULT_PORT

            # Validate connectivity to the device to provide immediate feedback
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=5
                )
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()
            except (OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                if await self._async_has_conflicting_host(host):
                    errors["host"] = "duplicate_ip"
                else:
                    await self.async_set_unique_id(f"{DOMAIN}-{host}-{port}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=name,
                        data={CONF_HOST: host, CONF_PORT: port, CONF_NAME: name},
                    )

        default_name = self._get_default_name()
        if self._async_current_entries():
            schema = vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_NAME, default=default_name): str,
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_HOST, default="qube.local"): str,
                    vol.Required(CONF_NAME, default=default_name): str,
                }
            )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_host = user_input[CONF_HOST]
            new_name = user_input[CONF_NAME]
            port = DEFAULT_PORT
            new_unique_id = f"{DOMAIN}-{new_host}-{port}"

            # Check for duplicate unique_id with other entries
            for entry in self._async_current_entries():
                if entry.entry_id == reconfigure_entry.entry_id:
                    continue
                if entry.unique_id == new_unique_id:
                    return self.async_abort(reason="already_configured")

            # Check for conflicting host/IP
            if await self._async_has_conflicting_host(
                new_host, skip_entry_id=reconfigure_entry.entry_id
            ):
                errors["host"] = "duplicate_ip"
            else:
                # Validate connectivity
                try:
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection(new_host, port), timeout=5
                    )
                    writer.close()
                    with contextlib.suppress(Exception):
                        await writer.wait_closed()
                except (OSError, TimeoutError):
                    errors["base"] = "cannot_connect"

            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        CONF_HOST: new_host,
                        CONF_PORT: port,
                        CONF_NAME: new_name,
                    },
                    unique_id=new_unique_id,
                    title=new_name,
                )

        # Show form with current values as defaults
        data = reconfigure_entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=data.get(CONF_HOST)): str,
                vol.Required(
                    CONF_NAME, default=data.get(CONF_NAME, reconfigure_entry.title)
                ): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )
