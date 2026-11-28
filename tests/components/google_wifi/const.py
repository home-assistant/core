"""Constants for the Google Wifi sensor platform tests."""

from typing import Any

from googlewifiapi.const import DEFAULT_HOST, ENDPOINT

RESOURCE_URL = f"http://{DEFAULT_HOST}{ENDPOINT}"

# All sample data is available at https://github.com/EReaso/GoogleWifiApi/issues/7


def build_response(
    *,
    software_version: str = "softwareVersion",
    update_new_version: str = "0.0.0.0",
    uptime: int = 86_400,
    online: bool = True,
    local_ip: str = "10.0.0.10",
    hardware_id: str = "GALE [REDACTED]",
    model_id: str = "modelId",
    group_role: str = "root",
    country_code: str = "us",
) -> dict[str, Any]:
    """Build a Google Wifi status response payload."""
    return {
        "dns": {"mode": "automatic", "servers": ["75.75.75.75", "75.75.76.76"]},
        "setupState": "GWIFI_OOBE_COMPLETE",
        "software": {
            "blockingUpdate": 1,
            "softwareVersion": software_version,
            "updateChannel": "stable-channel",
            "updateNewVersion": update_new_version,
            "updateProgress": 0.0,
            "updateRequired": False,
            "updateStatus": "idle",
        },
        "system": {
            "countryCode": country_code,
            "groupRole": group_role,
            "hardwareId": hardware_id,
            "lan0Link": False,
            "ledAnimation": "CONNECTED",
            "ledIntensity": 6,
            "modelId": model_id,
            "oobeDetailedStatus": "JOIN_AND_REGISTRATION_STAGE_DEVICE_ONLINE",
            "uptime": uptime,
        },
        "vorlonInfo": {"migrationMode": "voobed"},
        "wan": {
            "captivePortal": False,
            "ethernetLink": True,
            "gatewayIpAddress": "10.0.0.1",
            "invalidCredentials": False,
            "ipAddress": True,
            "ipMethod": "dhcp",
            "ipPrefixLength": 24,
            "leaseDurationSeconds": 1,
            "localIpAddress": local_ip,
            "nameServers": ["75.75.75.75", "75.75.76.76"],
            "online": online,
            "pppoeDetected": False,
            "vlanScanAttemptCount": 0,
            "vlanScanComplete": True,
        },
    }


DEFAULT_RESPONSE = build_response(
    software_version="softwareVersion",
    update_new_version="0.0.0.0",
    uptime=86_400,
    online=True,
    local_ip="10.0.0.10",
)

UPDATED_RESPONSE = build_response(
    software_version="newVersion",
    update_new_version="1.2.3.4",
    uptime=172_800,
    online=False,
    local_ip="10.0.0.11",
)

LEAF_RESPONSE = build_response(
    software_version="3.78.518349",
    uptime=519_060,
    online=True,
    local_ip="192.168.86.21",
    hardware_id="SIROCCO MP-MP1-[REDACTED]",
    model_id="SIROCCO",
    group_role="leaf",
    country_code="au",
)

SPEAKER_RESPONSE = build_response(
    software_version="1.56.514310",
    uptime=129_345,
    online=False,
    local_ip="",
    hardware_id="vento-b4",
    model_id="VENTO",
    group_role="none",
    country_code="AU",
)
SPEAKER_RESPONSE["dns"] = {"mode": "automatic", "servers": []}
SPEAKER_RESPONSE["setupNetwork"] = {"ssid": ""}
SPEAKER_RESPONSE["software"]["updateProgress"] = -1.0
SPEAKER_RESPONSE["system"]["lan0Link"] = False
SPEAKER_RESPONSE["wan"] = {
    "captivePortal": False,
    "ethernetLink": False,
    "invalidCredentials": False,
    "ipAddress": False,
    "online": False,
    "pppoeDetected": False,
    "vlanScanAttemptCount": 0,
    "vlanScanComplete": False,
}
