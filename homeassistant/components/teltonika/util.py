"""Utility helpers for the Teltonika integration."""

from __future__ import annotations

API_SUFFIX = "/api"


def candidate_base_urls(host: str) -> list[str]:
    """Return candidate base URLs for the Teltonika device.

    The Teltonika API lives under the ``/api`` path and can be accessed over
    HTTPS or HTTP. We try to use HTTPS whenever possible but fall back to
    HTTP if the device is not accessible over HTTPS.
    """

    host_input = host.strip().rstrip("/")

    if host_input.startswith(("http://", "https://")):
        scheme, raw_host = host_input.split("://", 1)
        base = raw_host.removesuffix(API_SUFFIX)
        if scheme == "https":
            return [f"https://{base}{API_SUFFIX}", f"http://{base}{API_SUFFIX}"]
        return [f"http://{base}{API_SUFFIX}", f"https://{base}{API_SUFFIX}"]

    base_host = host_input.removesuffix(API_SUFFIX)
    return [
        f"https://{base_host}{API_SUFFIX}",
        f"http://{base_host}{API_SUFFIX}",
    ]


def base_url_to_host(base_url: str) -> str:
    """Return the host value stored in the config entry for the given base URL."""
    return base_url.rstrip("/").removesuffix(API_SUFFIX)
