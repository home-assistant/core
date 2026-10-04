"""Constants for the Google Wifi sensor platform tests."""

from typing import Any

from googlewifiapi.const import DEFAULT_HOST, ENDPOINT

RESOURCE_URL = f"http://{DEFAULT_HOST}{ENDPOINT}"


def build_response(
    *,
    software_version: str,
    update_status: str,
    uptime: int,
    online: bool,
    local_ip: str,
) -> dict[str, Any]:
    """Build a Google Wifi status response payload."""
    return {
        "dns": {"mode": "automatic", "servers": ["75.75.75.75", "75.75.76.76"]},
        "software": {
            "softwareVersion": software_version,
            "updateStatus": update_status,
            "updateRequired": False,
            "updateProgress": 0.0,
        },
        "system": {
            "countryCode": "us",
            "modelId": "modelId",
            "uptime": uptime,
        },
        "wan": {
            "online": online,
            "ethernetLink": True,
            "gatewayIpAddress": "10.0.0.1",
            "localIpAddress": local_ip,
            "ipMethod": "dhcp",
            "ipPrefixLength": 24,
            "nameServers": ["75.75.75.75", "75.75.76.76"],
        },
    }


DEFAULT_RESPONSE = build_response(
    software_version="softwareVersion",
    update_status="idle",
    uptime=86_400,
    online=True,
    local_ip="10.0.0.10",
)

UPDATED_RESPONSE = build_response(
    software_version="newVersion",
    update_status="latest",
    uptime=172_800,
    online=False,
    local_ip="10.0.0.11",
)
