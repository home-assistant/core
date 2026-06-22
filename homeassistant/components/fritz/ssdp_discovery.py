"""SSDP discovery helpers for FRITZ! integrations."""

import ipaddress
import socket
from urllib.parse import urlparse
from uuid import UUID

from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo

FRITZ_BOX_HOST = "fritz.box"


def parse_device_uuid(value: str) -> str | None:
    """Return a normalized UUID string, or None if the value is not a UUID."""
    value = value.strip()
    if not value:
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


def uuid_from_upnp_udn(raw_udn: str) -> str | None:
    """Parse UPnP UDN (``uuid:<uuid>``)."""
    return parse_device_uuid(raw_udn.removeprefix("uuid:"))


def uuid_from_ssdp_usn(usn: str) -> str | None:
    """Parse device UUID from SSDP USN (``uuid:<uuid>::...``)."""
    if not usn.startswith("uuid:"):
        return None
    return uuid_from_upnp_udn(usn.split("::", 1)[0])


def hostname_from_url(url: str) -> str | None:
    """Return hostname from a URL, or None if parsing fails."""
    try:
        return urlparse(url).hostname
    except ValueError:
        return None


def uuid_from_discovery(discovery_info: SsdpServiceInfo) -> str | None:
    """Device UUID from UPnP UDN or SSDP USN."""
    if raw_udn := discovery_info.upnp.get(ATTR_UPNP_UDN):
        if device_uuid := uuid_from_upnp_udn(raw_udn):
            return device_uuid
    if discovery_info.ssdp_usn:
        if device_uuid := uuid_from_ssdp_usn(discovery_info.ssdp_usn):
            return device_uuid
    return None


def unique_id_for_discovery(discovery_info: SsdpServiceInfo, host: str) -> str:
    """Config-flow unique_id: device UUID if present, else host."""
    return uuid_from_discovery(discovery_info) or host


def is_link_local_host(host: str) -> bool:
    """Return True if host is a link-local IP address."""
    try:
        return ipaddress.ip_address(host).is_link_local
    except ValueError:
        return False


def host_from_ssdp_usn(usn: str) -> str | None:
    """Return fritz.box when embedded in a non-standard USN URL segment."""
    search_start = 0
    while (scheme_pos := usn.find("://", search_start)) != -1:
        fragment_start = scheme_pos + 1
        fragment_end = fragment_start
        while fragment_end < len(usn) and usn[fragment_end] not in " \t\r\n":
            if (
                fragment_end > fragment_start
                and usn[fragment_end : fragment_end + 2] == "::"
            ):
                break
            fragment_end += 1
        fragment = usn[fragment_start:fragment_end]
        if hostname := hostname_from_url(f"http:{fragment}"):
            if hostname.lower() == FRITZ_BOX_HOST:
                return FRITZ_BOX_HOST
        search_start = scheme_pos + 3
    return None


def host_from_ssdp(discovery_info: SsdpServiceInfo) -> str | None:
    """Host from SSDP location, headers, or USN."""
    if discovery_info.ssdp_location:
        if hostname := hostname_from_url(discovery_info.ssdp_location):
            return hostname
    if discovery_info.ssdp_headers:
        location_header = discovery_info.ssdp_headers.get("location")
        if isinstance(location_header, str):
            if hostname := hostname_from_url(location_header):
                return hostname
    if discovery_info.ssdp_usn:
        return host_from_ssdp_usn(discovery_info.ssdp_usn)
    return None


def is_placeholder_unique_id(
    unique_id: str | None,
    discovered_host: str,
    config_host: str | None,
    *,
    resolved_hosts: frozenset[str] | None = None,
) -> bool:
    """True if unique_id is unset or a host placeholder eligible for UUID migration."""
    if unique_id is None:
        return True
    placeholders = {discovered_host}
    if config_host is not None:
        placeholders.add(config_host)
    if resolved_hosts is not None:
        placeholders |= resolved_hosts
    return unique_id in placeholders


def resolve_host_ips(*hosts: str | None) -> frozenset[str]:
    """Resolve hostnames to IPv4; skip unresolvable hosts."""
    resolved: set[str] = set()
    for host in hosts:
        if not host:
            continue
        try:
            resolved.add(socket.gethostbyname(host))
        except OSError:
            continue
    return frozenset(resolved)
