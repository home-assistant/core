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
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_FRIENDLY_NAME_LANGUAGE,
    CONF_HOST,
    CONF_LABEL,
    CONF_PORT,
    CONF_SHOW_LABEL_IN_NAME,
    CONF_UNIT_ID,
    DEFAULT_FRIENDLY_NAME_LANGUAGE,
    DEFAULT_PORT,
    DOMAIN,
)

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
    _reconfig_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return OptionsFlowHandler(config_entry)

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
                        title=f"Qube Heat Pump ({host})",
                        data={CONF_HOST: host, CONF_PORT: port},
                    )

        if self._async_current_entries():
            schema = vol.Schema({vol.Required(CONF_HOST): str})
        else:
            schema = vol.Schema({vol.Required(CONF_HOST, default="qube.local"): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, entry_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        # Called when reconfigure flow is started; entry may be provided in context or data
        if entry_data and isinstance(entry_data, dict):
            eid = entry_data.get("entry_id")
            if eid:
                self._reconfig_entry = self.hass.config_entries.async_get_entry(eid)
        if self._reconfig_entry is None:
            # Try to get from context
            eid = (self.context or {}).get("entry_id")
            if eid:
                self._reconfig_entry = self.hass.config_entries.async_get_entry(eid)
        if self._reconfig_entry is None:
            return self.async_abort(reason="unknown_entry")

        # Show form
        data = self._reconfig_entry.data
        host = data.get(CONF_HOST)
        port = data.get(CONF_PORT, DEFAULT_PORT)
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=host): str,
                vol.Required(CONF_PORT, default=port): int,
            }
        )
        return self.async_show_form(step_id="reconfigure_confirm", data_schema=schema)

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration confirmation."""
        if self._reconfig_entry is None:
            return self.async_abort(reason="unknown_entry")
        # Update entry data
        new_host = user_input[CONF_HOST]
        new_port = user_input[CONF_PORT]
        new_unique_id = f"{DOMAIN}-{new_host}-{new_port}"
        for entry in self._async_current_entries():
            if entry.entry_id == self._reconfig_entry.entry_id:
                continue
            if entry.unique_id == new_unique_id:
                return self.async_abort(reason="already_configured")

        if await self._async_has_conflicting_host(
            new_host, skip_entry_id=self._reconfig_entry.entry_id
        ):
            return self.async_abort(reason="duplicate_ip")

        new = dict(self._reconfig_entry.data)
        new[CONF_HOST] = new_host
        new[CONF_PORT] = new_port
        self.hass.config_entries.async_update_entry(
            self._reconfig_entry,
            data=new,
            title=f"Qube Heat Pump ({new_host})",
            unique_id=new_unique_id,
        )
        # Reload
        await self.hass.config_entries.async_reload(self._reconfig_entry.entry_id)
        return self.async_abort(reason="reconfigured")


class OptionsFlowHandler(OptionsFlow):
    """Options flow for Qube Heat Pump."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current_host = str(self._entry.data.get(CONF_HOST, "qube.local")).strip()
        current_port = int(self._entry.data.get(CONF_PORT, DEFAULT_PORT))
        # Capture existing entries to support duplicate IP detection
        entries = [
            e
            for e in self.hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != self._entry.entry_id
        ]

        current_unit = int(
            self._entry.options.get(CONF_UNIT_ID, self._entry.data.get(CONF_UNIT_ID, 1))
        )
        current_label_option = bool(
            self._entry.options.get(CONF_SHOW_LABEL_IN_NAME, False)
        )

        hub_entry = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        resolved_ip = None
        hub = hub_entry.get("hub")
        if hub is not None:
            resolved_ip = getattr(hub, "resolved_ip", None) or getattr(
                hub, "host", None
            )
        if not resolved_ip:
            resolved_ip = await _async_resolve_host(current_host)

        if user_input is not None:
            user_input = dict(user_input)
            new_host = str(user_input.get(CONF_HOST, current_host)).strip()
            show_label = bool(user_input.get(CONF_SHOW_LABEL_IN_NAME, False))

            if not new_host:
                errors[CONF_HOST] = "invalid_host"
            else:
                conflict = await _async_find_conflicting_entry(entries, new_host)
                if conflict:
                    errors[CONF_HOST] = "duplicate_ip"

            host_changed = new_host != current_host
            if host_changed and CONF_HOST not in errors:
                try:
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection(new_host, current_port),
                        timeout=5,
                    )
                    writer.close()
                    with contextlib.suppress(Exception):
                        await writer.wait_closed()
                except (OSError, TimeoutError):
                    errors[CONF_HOST] = "cannot_connect"

            if not errors:
                opts = dict(self._entry.options)
                opts.pop(CONF_UNIT_ID, None)
                opts[CONF_SHOW_LABEL_IN_NAME] = show_label
                opts[CONF_LABEL] = user_input.get(CONF_LABEL, "")
                opts[CONF_FRIENDLY_NAME_LANGUAGE] = user_input.get(
                    CONF_FRIENDLY_NAME_LANGUAGE, DEFAULT_FRIENDLY_NAME_LANGUAGE
                )

                update_kwargs: dict[str, Any] = {"options": opts}
                if host_changed:
                    new_data = dict(self._entry.data)
                    new_data[CONF_HOST] = new_host
                    new_data[CONF_PORT] = current_port
                    update_kwargs["data"] = new_data
                    update_kwargs["title"] = f"Qube Heat Pump ({new_host})"
                    update_kwargs["unique_id"] = f"{DOMAIN}-{new_host}-{current_port}"
                self.hass.config_entries.async_update_entry(
                    self._entry, **update_kwargs
                )
                if host_changed:
                    device_registry = dr.async_get(self.hass)
                    identifiers = {(DOMAIN, f"{current_host}:{current_unit}")}
                    old_device = device_registry.async_get_device(identifiers)
                    if old_device:
                        device_registry.async_remove_device(old_device.id)
                    await self.hass.config_entries.async_reload(self._entry.entry_id)
                return self.async_create_entry(title="", data=opts)

        current_label = self._entry.options.get(
            CONF_LABEL, self._entry.data.get(CONF_LABEL, "")
        )
        current_language = self._entry.options.get(
            CONF_FRIENDLY_NAME_LANGUAGE, DEFAULT_FRIENDLY_NAME_LANGUAGE
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Optional(CONF_LABEL, default=current_label): str,
                vol.Optional(
                    CONF_SHOW_LABEL_IN_NAME, default=current_label_option
                ): bool,
                vol.Optional(
                    CONF_FRIENDLY_NAME_LANGUAGE, default=current_language
                ): vol.In(["en", "nl"]),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "resolved_ip": resolved_ip or "unknown",
            },
        )
