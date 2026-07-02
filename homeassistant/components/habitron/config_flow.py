"""Config flow for Habitron integration."""

import asyncio
import contextlib
import json
import logging
import socket
from typing import Any, override
from urllib.parse import urlparse

from habitron_client import test_connection
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import network
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import CONF_DEFAULT_HOST, DOMAIN
from .coordinator import HabitronConfigEntry

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PORT = 7777
DISCOVERY_TIMEOUT = 3.0
DISCOVERY_MESSAGE = b"habitron_discovery"

KEY_HOST = "habitron_host"
KEY_TOKEN = "websock_token"


async def _get_local_ip(hass: HomeAssistant) -> str:
    """Get the local IP address using HA network utilities."""
    try:
        return await network.async_get_source_ip(hass, target_ip="8.8.8.8")
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    # 1. Local IP Check
    own_ip = await _get_local_ip(hass)
    _LOGGER.debug("Smart Center own IP: %s", own_ip)

    host_input = data[KEY_HOST]

    # If the entered IP matches our own IP, save as 'local'
    if host_input == own_ip:
        host_input = "local"
        data[KEY_HOST] = "local"

    host_to_test = host_input
    if host_to_test == "local":
        host_to_test = own_ip

    # 2. Basic Validation
    if len(host_to_test) < 4:
        raise InvalidHost

    # 3. Connection Test
    try:
        # test_connection has been async since habitron_client 1.0.0.
        result, host_name = await test_connection(host_to_test)
    except socket.gaierror as exc:
        raise HostNotFound from exc
    except ConnectionRefusedError as exc:
        raise CannotConnect from exc
    except Exception as exc:
        _LOGGER.error("Connection error: %s", exc)
        raise CannotConnect from exc

    if not result:
        raise CannotConnect

    return {"title": host_name}


class UDPDiscoveryProtocol(asyncio.DatagramProtocol):
    """Protocol to discover Habitron devices via UDP."""

    def __init__(self) -> None:
        """Initialize the protocol."""
        self.found_devices: list[dict[str, Any]] = []
        self.transport: asyncio.DatagramTransport | None = None

    @override
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Set up transport for broadcast."""
        assert isinstance(transport, asyncio.DatagramTransport)
        self.transport = transport
        sock = transport.get_extra_info("socket")
        if sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Send discovery packet
        if self.transport:
            self.transport.sendto(
                DISCOVERY_MESSAGE, ("255.255.255.255", DISCOVERY_PORT)
            )

    @override
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming discovery response."""
        try:
            resp = json.loads(data.decode())
            if "host" in resp and "ip" in resp:
                if not any(d.get("ip") == resp["ip"] for d in self.found_devices):
                    self.found_devices.append(resp)
        except Exception:  # noqa: BLE001
            # Malformed discovery responses are routine — best to ignore the
            # individual packet and keep listening for the rest.
            pass

    @override
    def error_received(self, exc: Exception) -> None:
        """Handle errors."""
        _LOGGER.debug("UDP Discovery error: %s", exc)

    @override
    def connection_lost(self, exc: Exception | None) -> None:
        """Handle connection lost."""


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for habitron."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: dict[str, Any] = {}
        self._udp_devices: list[dict[str, Any]] | None = None

    async def _cached_discover(self) -> list[dict[str, Any]]:
        """Run the UDP scan once per flow and reuse the result.

        The scan blocks for ``DISCOVERY_TIMEOUT``; the user step would otherwise
        run it both when showing the form and again on submit.
        """
        if self._udp_devices is None:
            self._udp_devices = await self._discover_habitron()
        return self._udp_devices

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: HabitronConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler()

    def _is_device_already_configured(self, host: str, ip: str | None = None) -> bool:
        """Check if a device with this host or IP is already configured."""
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in existing_entries:
            entry_host = entry.data.get(KEY_HOST)
            if entry_host == host or (ip and entry_host == ip):
                return True
        return False

    async def _discover_habitron(self) -> list[dict[str, Any]]:
        """Run a quick UDP scan to find devices."""
        loop = asyncio.get_running_loop()
        try:
            transport, protocol = await loop.create_datagram_endpoint(
                UDPDiscoveryProtocol,
                local_addr=("0.0.0.0", 0),
                family=socket.AF_INET,
            )
        except OSError as err:
            _LOGGER.error("Could not start UDP discovery: %s", err)
            return []

        try:
            await asyncio.sleep(DISCOVERY_TIMEOUT)
        finally:
            transport.close()

        # ``create_datagram_endpoint`` infers the concrete protocol type from the
        # factory, so ``protocol`` is a UDPDiscoveryProtocol here.
        return protocol.found_devices

    @override
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle SSDP discovery."""
        host = (
            urlparse(discovery_info.ssdp_location).hostname
            if discovery_info.ssdp_location
            else None
        )
        if not host:
            return self.async_abort(reason="no_host_in_ssdp")
        host_str = str(host)

        # Prefer stable identifiers from the UPnP description; fall back
        # to a UDP probe (which may return a serial), and only use the
        # host as last resort. A host-based id changes on DHCP-lease
        # renewals and would otherwise look like a new device.
        upnp = discovery_info.upnp or {}
        unique_id: str | None = upnp.get(ATTR_UPNP_UDN) or upnp.get(ATTR_UPNP_SERIAL)
        target_device: dict[str, Any] | None = None

        if unique_id is None:
            devices = await self._cached_discover()
            target_device = next((d for d in devices if d.get("ip") == host_str), None)
            if target_device:
                unique_id = target_device.get("serial")

        self._discovered_device = target_device or {"host": host_str, "ip": host_str}

        if not unique_id:
            _LOGGER.warning(
                "Habitron at %s exposed no UDN/serial; using host as fallback id",
                host_str,
            )
            unique_id = f"habitron_{host_str}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={KEY_HOST: host_str})

        # The unique_id did not match an existing entry. The same SmartHub
        # may already be configured under a host-based fallback id — the
        # manual step falls back to ``habitron_<host>`` when no serial is
        # available, while SSDP yields a stable UDN/serial. Match on the
        # host/IP so we adopt the stable id and abort instead of offering a
        # duplicate of the hub the user already added.
        candidate_hosts: set[str | None] = {
            host_str,
            self._discovered_device.get("ip"),
        }
        with contextlib.suppress(OSError):
            candidate_hosts.add(
                await self.hass.async_add_executor_job(socket.gethostbyname, host_str)
            )
        # An entry configured as the ``local`` sentinel runs on the same machine
        # as Home Assistant, so its LAN address is one of HA's own source IPs.
        # Ask HA directly — this matches even when the hub is briefly unreachable
        # (e.g. rebooting during startup) and the entry is not yet loaded.
        local_is_candidate = any(
            str(ip) in candidate_hosts
            for ip in await network.async_get_enabled_source_ips(self.hass)
        )
        for entry in self._async_current_entries(include_ignore=False):
            host_conf = entry.data.get(KEY_HOST)
            if host_conf in candidate_hosts or (
                host_conf == CONF_DEFAULT_HOST and local_is_candidate
            ):
                if entry.unique_id != unique_id:
                    self.hass.config_entries.async_update_entry(
                        entry, unique_id=unique_id
                    )
                return self.async_abort(reason="already_configured")

        self.context["title_placeholders"] = {"name": host_str}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            # Create entry with discovered data
            data = {
                KEY_HOST: self._discovered_device.get(
                    "host", self._discovered_device.get("ip")
                ),
                KEY_TOKEN: "",
            }
            try:
                info = await validate_input(self.hass, data)
                return self.async_create_entry(title=info["title"], data=data)
            except Exception:  # noqa: BLE001
                return self.async_abort(reason="unknown")

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self._discovered_device.get("host", "Habitron Hub")
            },
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        default_host = CONF_DEFAULT_HOST

        # Pre-fill with discovery if just opened
        if user_input is None:
            discovered = await self._cached_discover()

            # Filter: Keep only devices that are NOT yet configured
            valid_devices = [
                d
                for d in discovered
                if not self._is_device_already_configured(
                    d.get("host", ""), d.get("ip")
                )
            ]
            if valid_devices:
                device = valid_devices[0]
                default_host = device.get("host", device.get("ip", CONF_DEFAULT_HOST))

        if user_input is not None:
            # Try a UDP probe to obtain a stable serial-based unique_id;
            # fall back to the host string when no probe response arrives.
            host_input = user_input[KEY_HOST]
            unique_id: str | None = None
            devices = await self._cached_discover()
            target = next(
                (
                    d
                    for d in devices
                    if d.get("ip") == host_input or d.get("host") == host_input
                ),
                None,
            )
            if target:
                unique_id = target.get("serial")
            if unique_id is None:
                unique_id = f"habitron_{host_input}"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except HostNotFound:
                errors["base"] = "host_not_found"
            except InvalidHost:
                errors["base"] = "host_not_found"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            default_host = user_input[KEY_HOST]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(KEY_HOST, default=default_host): str,
                    vol.Optional(KEY_TOKEN, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Re-configure an existing Habitron entry.

        Lets the user change the SmartHub host (e.g. after a hardware
        swap or static-IP migration) without removing the entry — the
        ``unique_id`` and device-registry mappings stay intact, the
        platforms reload after the update.
        """
        errors: dict[str, str] = {}
        existing = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except HostNotFound:
                errors["base"] = "host_not_found"
            except InvalidHost:
                errors["base"] = "host_not_found"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected reconfigure error")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    existing, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(KEY_HOST, default=existing.data.get(KEY_HOST)): str,
                    vol.Optional(
                        KEY_TOKEN, default=existing.data.get(KEY_TOKEN, "")
                    ): str,
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Allow to change options of integration while running."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)

                # Update Config Entry Data (Host/IP)
                # Note: Host change in OptionsFlow needs reload normally
                # Persisting the new host/token fires the entry update
                # listener, which reloads the entry exactly once. Don't reload
                # again here (that caused two extra reloads).
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=user_input,
                )
                return self.async_create_entry(title="", data={})
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Options flow error")
                errors["base"] = "unknown"

        current_config = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(KEY_HOST, default=current_config.get(KEY_HOST)): str,
                    vol.Optional(
                        KEY_TOKEN, default=current_config.get(KEY_TOKEN, "")
                    ): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class HostNotFound(exceptions.HomeAssistantError):
    """Error to indicate DNS name is not found."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
