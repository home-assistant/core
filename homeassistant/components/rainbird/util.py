"""Helpers for the Rain Bird integration."""

from __future__ import annotations

from urllib.parse import urlsplit


def normalize_rainbird_host(host: str) -> str:
    """Normalize the host to a hostname/IP (optionally with a port).

    The Rain Bird config flow has historically accepted values like `192.0.2.1`
    and `http://192.0.2.1`. The pyrainbird controller discovery expects just the
    hostname/IP, so strip any scheme/path while preserving an explicit port.
    """
    host = host.strip().rstrip("/")

    if "://" not in host and not host.startswith("//"):
        return host

    parsed = urlsplit(host)
    if parsed.hostname is None:
        return host

    if parsed.port is None:
        return parsed.hostname

    return f"{parsed.hostname}:{parsed.port}"

