"""Tests for the Nmap Tracker integration."""

from typing import Any

CLIENT_MAC = "aa:bb:cc:dd:ee:ff"
CLIENT_IP = "192.168.1.2"


def scan_result(hostname: str | None) -> dict[str, Any]:
    """Return an nmap scan result with the client up.

    Without a hostname, nmap reports no hostnames at all.
    """
    return {
        "scan": {
            CLIENT_IP: {
                "status": {"state": "up", "reason": "arp-response"},
                "addresses": {"mac": CLIENT_MAC.upper()},
                "hostnames": []
                if hostname is None
                else [{"name": hostname, "type": "PTR"}],
                "vendor": {CLIENT_MAC.upper(): "Vendor"},
            }
        }
    }
