"""Network utilities."""
from ipaddress import ip_address, ip_network


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


def is_local(address) -> bool:
    """Check if an address is local."""
    return address in LOCAL_IPS or \
        any(address in network for network in LOCAL_NETWORKS)
