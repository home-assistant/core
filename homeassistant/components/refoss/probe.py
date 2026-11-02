"""Build Refoss discovery probe targets."""

from collections.abc import Iterable, Mapping
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
from typing import Any

from .const import CONF_NETWORKS, LIMITED_BROADCAST, MAX_NETWORKS, NETWORK_PREFIX


def normalize_networks(raw: str) -> list[str] | None:
    """Validate comma-separated IPv4 hosts and /24 networks.

    English and Chinese commas are accepted. Newlines are treated as commas.

    Returns a sorted unique list, or None when any item is invalid.
    """
    normalized: set[str] = set()
    items = raw.replace("，", ",").replace("\r\n", "\n").replace("\n", ",")
    for item in items.split(","):
        item = item.strip()
        if not item:
            continue
        parsed = _normalize_network_line(item)
        if parsed is None:
            return None
        normalized.add(parsed)
    if len(normalized) > MAX_NETWORKS:
        return None
    return sorted(normalized)


def networks_from_options(options: Mapping[str, Any]) -> list[str]:
    """Return configured networks stored on a config entry."""
    raw = options.get(CONF_NETWORKS, [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def build_probe_addresses(
    networks: list[str],
    *,
    local_broadcasts: Iterable[str],
    known_ips: Iterable[str],
    include_hosts: bool,
) -> list[str]:
    """Return discovery targets, optionally expanding configured subnets."""
    addresses = [LIMITED_BROADCAST, *local_broadcasts]
    for network in networks:
        if "/" not in network:
            addresses.append(network)
            continue
        parsed = ip_network(network)
        if not isinstance(parsed, IPv4Network):
            continue
        addresses.append(str(parsed.broadcast_address))
        if include_hosts:
            addresses.extend(_subnet_hosts(parsed))
    addresses.extend(known_ips)
    return list(dict.fromkeys(addresses))


def _normalize_network_line(line: str) -> str | None:
    """Return a canonical host or network, or None when the line is invalid."""
    if "/" in line:
        try:
            network = ip_network(line, strict=False)
        except ValueError:
            return None
        if not isinstance(network, IPv4Network) or network.prefixlen != NETWORK_PREFIX:
            return None
        return str(network)

    try:
        address = ip_address(line)
    except ValueError:
        return None
    if not isinstance(address, IPv4Address):
        return None
    return str(address)


def _subnet_hosts(network: IPv4Network) -> Iterable[str]:
    """Yield unicast addresses for a subnet sweep."""
    if network.prefixlen >= 31:
        return [str(address) for address in network]
    return [str(address) for address in network.hosts()]
