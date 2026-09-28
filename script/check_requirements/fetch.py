"""Shared HTTP and URL helpers for the deterministic requirement checks."""

from collections.abc import Mapping
import logging
from types import MappingProxyType
from typing import Any
from urllib.parse import urlparse

import requests

_LOGGER = logging.getLogger(__name__)

# Shared across modules, so hand out a view callers cannot mutate.
HEADERS: Mapping[str, str] = MappingProxyType(
    {
        "User-Agent": "home-assistant-check-requirements/1.0",
        "Accept": "application/json",
    }
)
TIMEOUT = 30.0

# Source-code hosts we know. Matched against the URL's netloc (not a substring
# of the full URL) to avoid accepting `https://evil.com/?x=github.com`.
HOSTS = ("github.com", "gitlab.com", "codeberg.org")


def _netloc(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def host_of(url: str) -> str | None:
    """Return the known code host serving `url`, matched exactly.

    A subdomain is not the host: `gist.github.com` serves no repositories, so
    resolving it to `github.com` would query an unrelated project.
    """
    netloc = _netloc(url)
    return netloc if netloc in HOSTS else None


def is_known_host(url: str) -> bool:
    """True if `url` is on a known code host or a subdomain of one."""
    netloc = _netloc(url)
    return any(netloc == host or netloc.endswith(f".{host}") for host in HOSTS)


def _decode(response: requests.Response, url: str) -> dict[str, Any] | None:
    """Return the JSON object in `response`, or None if there isn't one."""
    if response.status_code == 404:
        return None
    if not response.ok:
        _LOGGER.warning("HTTP %s fetching %s", response.status_code, url)
        return None
    try:
        data = response.json()
    except ValueError as err:
        _LOGGER.warning("Invalid JSON at %s: %s", url, err)
        return None
    return data if isinstance(data, dict) else None


def get_json(
    url: str, headers: Mapping[str, str] | None = None
) -> dict[str, Any] | None:
    """Fetch JSON or return None on 404/network error."""
    try:
        response = requests.get(url, headers=headers or HEADERS, timeout=TIMEOUT)
    except requests.RequestException as err:
        _LOGGER.warning("Failed to fetch %s: %s", url, err)
        return None
    return _decode(response, url)


def post_json(
    url: str, payload: dict[str, Any], headers: Mapping[str, str] | None = None
) -> dict[str, Any] | None:
    """POST `payload` as JSON and return the response, or None on error."""
    try:
        response = requests.post(
            url, json=payload, headers=headers or HEADERS, timeout=TIMEOUT
        )
    except requests.RequestException as err:
        _LOGGER.warning("Failed to post to %s: %s", url, err)
        return None
    return _decode(response, url)
