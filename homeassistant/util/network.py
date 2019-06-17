"""Network utilities."""
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
import re
import subprocess
from typing import Optional, Union

# IP addresses of loopback interfaces
LOCAL_IPS = (
    ip_address('127.0.0.1'),
    ip_address('::1'),
)

# RFC1918 - Address allocation for Private Internets
LOCAL_NETWORKS = (
    ip_network('10.0.0.0/8'),
    ip_network('172.16.0.0/12'),
    ip_network('192.168.0.0/16'),
)


def is_local(address: Union[IPv4Address, IPv6Address]) -> bool:
    """Check if an address is local."""
    return address in LOCAL_IPS or \
        any(address in network for network in LOCAL_NETWORKS)


def get_mac_address(ip_address: str) -> Optional[str]:  # noqa: E501 pylint: disable=redefined-outer-name
    """Get MAC address for an IP address."""
    proc = subprocess.run(("arp", "-n", ip_address), stdout=subprocess.PIPE)
    match = re.search(br"\b(([0-9a-f]{1,2}\:){5}[0-9a-f]{1,2})\b",
                      proc.stdout, re.IGNORECASE)
    if match:
        return ":".join(
            x.zfill(2) for x in match.group(1).decode().split(":"))
    return None
