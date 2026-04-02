"""Config flow for deako."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

from pydeako import Deako, FindDevicesError
import voluptuous as vol
from zeroconf import ServiceBrowser, ServiceListener
from zeroconf import Zeroconf as Zeroconf_

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_KNOWN_BRIDGES,
    CONF_SECONDARY_HOST,
    DEAKO_DEFAULT_PORT,
    DOMAIN,
    NAME,
)

_LOGGER = logging.getLogger(__name__)

# How long to wait for zeroconf to discover bridges
DISCOVERY_TIMEOUT_S = 5
DISCOVERY_POLL_S = 0.5
DEAKO_MDNS_TYPE = "_deako._tcp.local."

MANUAL_ENTRY = "manual"


class _BridgeInfo:
    """Info about a discovered Deako bridge."""

    def __init__(self, ip: str, port: int, serial: str, version: str, name: str):
        """Initialize bridge info."""
        self.ip = ip
        self.port = port
        self.serial = serial
        self.version = version
        self.name = name

    @property
    def display_label(self) -> str:
        """Return a human-readable label for this bridge."""
        parts = [self.ip]
        if self.serial:
            parts.append(f"SN: {self.serial}")
        if self.version:
            short_ver = (
                self.version.split("-")[0] if "-" in self.version else self.version
            )
            parts.append(f"v{short_ver}")
        if len(parts) > 1:
            return f"{parts[0]} ({', '.join(parts[1:])})"
        return parts[0]


class _BridgeDiscoveryListener(ServiceListener):
    """Listener that collects discovered service names from zeroconf.

    The callbacks run on a zeroconf thread, so we must NOT call
    zc.get_service_info() here — it can block the event loop and
    raise EventLoopBlocked.  Instead we just record service names
    and resolve them later from the async context.
    """

    def __init__(self) -> None:
        """Initialize."""
        self.service_names: list[tuple[str, str]] = []  # (type_, name)

    def add_service(self, zc: Zeroconf_, type_: str, name: str) -> None:
        """Handle discovered service — just record the name."""
        self.service_names.append((type_, name))

    def remove_service(self, zc: Zeroconf_, type_: str, name: str) -> None:
        """Handle removed service."""

    def update_service(self, zc: Zeroconf_, type_: str, name: str) -> None:
        """Handle updated service."""
        self.service_names.append((type_, name))


class DeakoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Deako config flow."""

    VERSION = 1

    discovered_host: str
    _discovered_bridges: dict[str, _BridgeInfo]

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._discovered_bridges = {}

    async def _async_discover_bridges(self) -> dict[str, _BridgeInfo]:
        """Discover all Deako bridges on the network with full info."""
        _zc = await zeroconf.async_get_instance(self.hass)
        listener = _BridgeDiscoveryListener()
        browser = ServiceBrowser(_zc, DEAKO_MDNS_TYPE, listener)

        elapsed = 0.0
        while elapsed < DISCOVERY_TIMEOUT_S:
            await asyncio.sleep(DISCOVERY_POLL_S)
            elapsed += DISCOVERY_POLL_S
            if len(listener.service_names) > 0:
                # Give more time for additional bridges to respond
                await asyncio.sleep(2.0)
                break

        browser.cancel()

        # Now resolve each discovered service name — safe to call
        # get_service_info here because we're in the async context
        # and the browser is already stopped.
        bridges: dict[str, _BridgeInfo] = {}
        for type_, name in listener.service_names:
            try:
                info = await self.hass.async_add_executor_job(
                    _zc.get_service_info, type_, name
                )
            except Exception:  # noqa: BLE001
                continue
            if info is None:
                continue
            for addr_bytes in info.addresses:
                ip = socket.inet_ntoa(addr_bytes)
                props = info.properties or {}
                serial = props.get(b"sn", b"").decode(
                    "utf-8", errors="replace"
                )
                version = props.get(b"version", b"").decode(
                    "utf-8", errors="replace"
                )
                bridges[ip] = _BridgeInfo(
                    ip=ip,
                    port=info.port or DEAKO_DEFAULT_PORT,
                    serial=serial,
                    version=version,
                    name=name,
                )
        return bridges

    async def _async_store_discovered_as_known(
        self, entry_data: dict, discovered: dict[str, _BridgeInfo]
    ) -> dict[str, dict[str, str]]:
        """Merge newly discovered bridges into known_bridges and return the merged dict."""
        known: dict[str, dict[str, str]] = dict(
            entry_data.get(CONF_KNOWN_BRIDGES, {})
        )
        for ip, bridge in discovered.items():
            known[ip] = {
                "serial": bridge.serial,
                "version": bridge.version,
            }
        return known

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user.

        Tries zeroconf discovery first. If bridges are found, shows a
        selection list. If none are found, falls back to manual IP entry.
        """
        if user_input is not None:
            # User submitted a selection from the discovered bridges list
            selected = user_input.get(CONF_HOST, "")
            if selected == MANUAL_ENTRY:
                return await self.async_step_manual()
            # Auto-discovery selection — create entry without storing
            # a host so setup uses zeroconf (avoids connect/disconnect churn)
            return self.async_create_entry(title=NAME, data={})

        # Try zeroconf discovery
        self._discovered_bridges = await self._async_discover_bridges()

        if self._discovered_bridges:
            # Build dropdown of discovered bridges
            options: dict[str, str] = {}
            for ip, bridge in self._discovered_bridges.items():
                options[ip] = bridge.display_label
            options[MANUAL_ENTRY] = "Enter IP manually..."

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): vol.In(options),
                    }
                ),
            )

        # No bridges discovered — go straight to manual entry
        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP entry (when zeroconf finds nothing or user opts in)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not host:
                errors["base"] = "cannot_connect"
            elif await self._async_validate_connection(host):
                return self.async_create_entry(
                    title=NAME,
                    data={CONF_HOST: host},
                )
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.discovered_host = discovery_info.host

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self.discovered_host})

        # Store this bridge in known_bridges for any existing entry
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            known: dict[str, dict[str, str]] = dict(
                entry.data.get(CONF_KNOWN_BRIDGES, {})
            )
            # Extract serial and version from discovery_info properties
            props = discovery_info.properties or {}
            serial = props.get("sn", "")
            version = props.get("version", "")
            known[discovery_info.host] = {
                "serial": serial,
                "version": version,
            }
            self.hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_KNOWN_BRIDGES: known},
            )

        self.context.update({"title_placeholders": {"name": NAME}})
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is not None:
            # Don't store the discovered host as a configured primary.
            # Let setup always use zeroconf discovery for auto-discovered
            # bridges. This avoids the connect/disconnect/reconnect pattern
            # that can lock up the bridge. The user can later assign a
            # primary bridge via reconfigure if they want direct IP mode.
            return self.async_create_entry(
                title=NAME,
                data={},
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": NAME,
                "host": self.discovered_host,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of bridge addresses.

        Simple text fields for IP and serial number. No zeroconf discovery
        in this flow — the user enters the IP/SN directly. If the device
        is offline, the health monitor retries every 30s for up to 48h.
        """
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None

        if user_input is not None:
            primary_ip = user_input.get(CONF_HOST, "").strip()
            secondary_ip = user_input.get(CONF_SECONDARY_HOST, "").strip()

            if not primary_ip:
                errors["base"] = "no_host"
            elif secondary_ip and secondary_ip == primary_ip:
                errors["base"] = "same_host"
            else:
                data: dict[str, Any] = {CONF_HOST: primary_ip}
                if CONF_KNOWN_BRIDGES in entry.data:
                    data[CONF_KNOWN_BRIDGES] = dict(entry.data[CONF_KNOWN_BRIDGES])
                else:
                    data[CONF_KNOWN_BRIDGES] = {}

                if secondary_ip:
                    data[CONF_SECONDARY_HOST] = secondary_ip

                _LOGGER.info(
                    "Reconfigure: primary=%s, secondary=%s",
                    primary_ip, secondary_ip or "none",
                )
                return self.async_update_reload_and_abort(
                    entry,
                    data=data,
                    reason="reconfigure_bridge_updated",
                )

        # Pre-populate from runtime data (actual connected bridges)
        current_primary_ip = entry.data.get(CONF_HOST, "")
        current_secondary_ip = entry.data.get(CONF_SECONDARY_HOST, "")

        rd = (
            entry.runtime_data
            if hasattr(entry, "runtime_data") and entry.runtime_data
            else None
        )
        if rd is not None:
            if rd.active_host and rd.active_host != "discovered":
                current_primary_ip = rd.active_host
            if rd.failover_host:
                current_secondary_ip = rd.failover_host

        # Guard: don't show the same device as both primary and failover
        if current_secondary_ip and current_secondary_ip == current_primary_ip:
            current_secondary_ip = ""

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=current_primary_ip
                    ): str,
                    vol.Optional(
                        CONF_SECONDARY_HOST, default=current_secondary_ip
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _async_validate_connection(self, host: str) -> bool:
        """Validate connection to Deako bridge."""

        async def get_address():
            """Return address in the format expected by pydeako."""
            return f"{host}:{DEAKO_DEFAULT_PORT}", NAME

        connection = Deako(get_address)
        try:
            await connection.connect()
            await connection.find_devices()
        except (FindDevicesError, OSError):
            return False
        finally:
            await connection.disconnect()
            # Give the bridge time to clean up the connection before
            # setup_entry opens a new one. Deako bridges can lock up
            # if connections are opened/closed in rapid succession.
            await asyncio.sleep(2)

        return bool(connection.get_devices())
