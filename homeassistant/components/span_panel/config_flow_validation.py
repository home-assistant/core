"""Validation helpers for Span Panel config flow."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from pathlib import Path
import socket
import ssl
import tempfile

from span_panel_api import (
    V2AuthResponse,
    detect_api_version,
    download_ca_cert,
    register_v2,
)
from span_panel_api.exceptions import (
    SpanPanelAPIError,
    SpanPanelConnectionError,
    SpanPanelTimeoutError,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util.network import is_ipv4_address

_LOGGER = logging.getLogger(__name__)


async def validate_host(
    hass: HomeAssistant,
    host: str,
    port: int = 80,
) -> bool:
    """Validate the host connection by probing the panel's status endpoint."""
    client = get_async_client(hass, verify_ssl=False)
    try:
        result = await detect_api_version(host, port=port, httpx_client=client)
    except (
        ValueError,
        OSError,
        SpanPanelAPIError,
        SpanPanelConnectionError,
        SpanPanelTimeoutError,
    ):
        return False
    if result.probe_failed:
        return False
    return result.api_version in ("v1", "v2")


def validate_ipv4_address(host: str) -> bool:
    """Validate that the host is an IPv4 address."""
    return is_ipv4_address(host)


async def validate_v2_passphrase(
    hass: HomeAssistant, host: str, passphrase: str, port: int = 80
) -> V2AuthResponse:
    """Validate a v2 panel passphrase and return MQTT credentials.

    Raises:
        SpanPanelAuthError: on invalid passphrase (401/403).
        SpanPanelConnectionError: on network/timeout failures.
        SpanPanelTimeoutError: on request timeout.

    """
    client = get_async_client(hass, verify_ssl=False)
    return await register_v2(
        host, "Home Assistant", passphrase, port=port, httpx_client=client
    )


def is_fqdn(host: str) -> bool:
    """Determine if host is a Fully Qualified Domain Name (not IP, not mDNS).

    Returns True for domain names like 'span.home.lan' or 'panel.example.com'.
    Returns False for IP addresses, mDNS (.local) names, and single-label hostnames.
    """
    if is_ipv4_address(host):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return False
    if host.endswith((".local", ".local.")):
        return False
    return "." in host


async def check_fqdn_tls_ready(
    hass: HomeAssistant, fqdn: str, mqtts_port: int, http_port: int = 80
) -> bool:
    """Check if the MQTTS server certificate includes the FQDN in its SAN.

    Downloads the CA certificate from the panel via HTTP, then attempts
    a TLS connection to the MQTTS port using the FQDN as server_hostname.
    If the TLS handshake succeeds with hostname verification, the panel
    has regenerated its certificate to include the FQDN.
    """
    client = get_async_client(hass, verify_ssl=False)
    try:
        ca_pem = await download_ca_cert(fqdn, port=http_port, httpx_client=client)
    except (
        OSError,
        SpanPanelAPIError,
        SpanPanelConnectionError,
        SpanPanelTimeoutError,
    ):
        return False

    loop = asyncio.get_running_loop()

    def _check() -> bool:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as tmp:
            tmp.write(ca_pem)
            ca_path = Path(tmp.name)
        try:
            ctx.load_verify_locations(str(ca_path))
            with (
                socket.create_connection((fqdn, mqtts_port), timeout=5) as sock,
                ctx.wrap_socket(sock, server_hostname=fqdn),
            ):
                return True
        except ssl.SSLCertVerificationError, ssl.SSLError, OSError, TimeoutError:
            return False
        finally:
            ca_path.unlink(missing_ok=True)

    return await loop.run_in_executor(None, _check)


async def validate_v2_proximity(
    hass: HomeAssistant, host: str, port: int = 80
) -> V2AuthResponse:
    """Validate v2 panel proximity (door bypass) and return MQTT credentials.

    Calls register_v2 without a passphrase, which triggers door-bypass
    registration. The panel accepts this when the user opens/closes the
    door 3 times within the proximity window.

    Raises:
        SpanPanelAuthError: if proximity was not proven (door not opened).
        SpanPanelConnectionError: on network/timeout failures.
        SpanPanelTimeoutError: on request timeout.

    """
    client = get_async_client(hass, verify_ssl=False)
    return await register_v2(host, "Home Assistant", port=port, httpx_client=client)
