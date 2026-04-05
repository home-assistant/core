"""Network probe helpers for Connectivity Monitor."""

from __future__ import annotations

import asyncio
import logging
import re
import socket
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    DEFAULT_PING_TIMEOUT,
    PROTOCOL_AD_DC,
    PROTOCOL_TCP,
    PROTOCOL_UDP,
)

try:
    import dns.resolver as dns_resolver

    HAVE_DNS = True
except ImportError:
    dns_resolver = None  # type: ignore[assignment]
    HAVE_DNS = False

_LOGGER = logging.getLogger(__name__)


class NetworkProbe:
    """Encapsulate network host preparation and protocol probes."""

    def __init__(self, hass: HomeAssistant, dns_server: str) -> None:
        """Initialize the network probe state."""
        self.hass = hass
        self._dns_server = dns_server
        self._resolver = None
        self._resolved_ips: dict[str, str | None] = {}
        self._mac_addresses: dict[str, str | None] = {}
        self._icmp_privileged: dict[str, bool | None] = {}
        self._icmp_import_failed = False

    async def async_prepare_host(self, host: str) -> None:
        """Populate cached resolution and MAC data for a network host."""
        if host not in self._resolved_ips:
            self._resolved_ips[host] = await self._resolve_host(host)

        resolved_ip = self._resolved_ips.get(host)
        if resolved_ip and resolved_ip not in self._mac_addresses:
            self._mac_addresses[resolved_ip] = await self._get_mac_address(resolved_ip)

    async def async_update_target(self, target: dict[str, Any]) -> dict[str, Any]:
        """Probe a TCP/UDP/ICMP network target."""
        host = target[CONF_HOST]
        protocol = target[CONF_PROTOCOL]
        result: dict[str, Any] = {
            "connected": False,
            "latency": None,
            "resolved_ip": None,
            "mac_address": None,
        }

        try:
            await self.async_prepare_host(host)
            resolved_ip = self._resolved_ips.get(host)
            if not resolved_ip:
                _LOGGER.error("Could not resolve hostname %s", host)
                return result

            result["resolved_ip"] = resolved_ip
            result["mac_address"] = self._mac_addresses.get(resolved_ip)

            if protocol in (PROTOCOL_TCP, PROTOCOL_AD_DC):
                latency = await self._async_test_tcp(resolved_ip, target[CONF_PORT])
            elif protocol == PROTOCOL_UDP:
                latency = await self._async_test_udp(resolved_ip, target[CONF_PORT])
            else:
                latency = await self._async_icmp_ping(host, resolved_ip)

            if latency is not None:
                result["connected"] = True
                result["latency"] = round(latency, 2)

        except (OSError, TimeoutError) as err:
            _LOGGER.error(
                "Update failed for %s:%s (%s): %s",
                host,
                target.get(CONF_PORT, "N/A"),
                protocol,
                err,
            )
            return result
        else:
            return result

    async def _async_test_tcp(self, resolved_ip: str, port: int) -> float | None:
        """Open a TCP connection and return latency in milliseconds."""
        try:
            start_time = self.hass.loop.time()
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(resolved_ip, port),
                timeout=5,
            )
            latency = (self.hass.loop.time() - start_time) * 1000
            writer.close()
            await writer.wait_closed()
        except (OSError, TimeoutError) as err:
            _LOGGER.debug("TCP connection failed for %s:%s: %s", resolved_ip, port, err)
            return None
        else:
            return latency

    async def _async_test_udp(self, resolved_ip: str, port: int) -> float | None:
        """Open a UDP socket and return latency in milliseconds."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            start_time = self.hass.loop.time()
            sock.settimeout(5)
            await self.hass.async_add_executor_job(sock.connect, (resolved_ip, port))
            return (self.hass.loop.time() - start_time) * 1000
        except (OSError, TimeoutError) as err:
            _LOGGER.debug("UDP connection failed for %s:%s: %s", resolved_ip, port, err)
            return None
        finally:
            sock.close()

    async def _async_icmp_ping(self, host: str, ip_address: str) -> float | None:
        """Ping a host using Home Assistant's built-in ICMP approach."""
        try:
            from icmplib import (  # noqa: PLC0415
                NameLookupError,
                SocketPermissionError,
                async_ping,
            )
        except ImportError as err:
            if not self._icmp_import_failed:
                _LOGGER.error(
                    "ICMP support is unavailable because icmplib is not installed. "
                    "Restart Home Assistant so the updated integration requirements can be installed: %s",
                    err,
                )
                self._icmp_import_failed = True
            return None

        privileged = self._icmp_privileged.get(host, True)
        try:
            response = await async_ping(
                ip_address,
                count=2,
                timeout=DEFAULT_PING_TIMEOUT,
                privileged=privileged,
            )
        except SocketPermissionError:
            if privileged is True:
                _LOGGER.debug(
                    "ICMP raw socket not permitted for %s, retrying unprivileged",
                    ip_address,
                )
                self._icmp_privileged[host] = False
                return await self._async_icmp_ping(host, ip_address)

            _LOGGER.debug("ICMP socket permission denied for %s", ip_address)
            return None
        except NameLookupError:
            _LOGGER.debug("ICMP lookup failed for %s", ip_address)
            return None
        except (OSError, RuntimeError) as err:
            _LOGGER.debug("ICMP ping failed for %s: %s", ip_address, err)
            return None

        self._icmp_privileged[host] = privileged
        if not response.is_alive or response.avg_rtt is None:
            return None

        return float(response.avg_rtt)

    async def _get_mac_address(self, ip: str) -> str | None:
        """Get MAC address for an IP."""
        try:
            cmd = "arp -n" if not hasattr(socket, "AF_HYPERV") else "arp -a"
            proc = await asyncio.create_subprocess_shell(
                f"{cmd} {ip}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode()

            mac_match = re.search(r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})", output)
            if mac_match:
                return mac_match.group(0).upper().replace("-", ":")

            _LOGGER.debug("No MAC address found in ARP for IP %s", ip)
        except (OSError, ValueError) as err:
            _LOGGER.error("Error getting MAC address for %s: %s", ip, err)
            return None
        else:
            return None

    async def _get_resolver(self):
        """Get a DNS resolver in executor."""
        if not HAVE_DNS or dns_resolver is None:
            return None

        resolver_module = dns_resolver

        if self._resolver is None:

            def _create_resolver():
                resolver = resolver_module.Resolver()
                resolver.nameservers = [self._dns_server]
                resolver.timeout = 2
                resolver.lifetime = 4
                return resolver

            self._resolver = await self.hass.async_add_executor_job(_create_resolver)

        return self._resolver

    async def _resolve_host(self, hostname: str) -> str | None:
        """Resolve hostname to IP address using configured DNS server."""
        try:
            try:
                socket.inet_pton(socket.AF_INET, hostname)
            except OSError, ValueError:
                pass
            else:
                return hostname

            try:
                socket.inet_pton(socket.AF_INET6, hostname)
            except OSError, ValueError:
                pass
            else:
                return hostname

            resolver = await self._get_resolver()
            if resolver is None:
                _LOGGER.debug("DNS resolver unavailable for host %s", hostname)
                return None

            def _do_resolve():
                try:
                    answers = resolver.resolve(hostname, "A")
                    if answers:
                        return str(answers[0])
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("DNS resolution failed: %s", err)
                    return None
                else:
                    return None

            result = await self.hass.async_add_executor_job(_do_resolve)

            if result:
                _LOGGER.debug(
                    "Resolved %s to %s using DNS server %s",
                    hostname,
                    result,
                    self._dns_server,
                )
                return result

            _LOGGER.warning(
                "Could not resolve %s using DNS server %s",
                hostname,
                self._dns_server,
            )
        except (OSError, RuntimeError) as err:
            _LOGGER.error("Error resolving hostname %s: %s", hostname, err)
            return None
        return None
