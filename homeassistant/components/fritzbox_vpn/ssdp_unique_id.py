"""SSDP helpers (aligned with homeassistant/components/fritz/config_flow)."""

from urllib.parse import urlparse
from uuid import UUID

from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo

from .const import FRITZBOX_SSDP_INDICATORS, REPEATER_INDICATORS


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
    return parse_device_uuid(raw_udn.removeprefix("uuid:"))


def uuid_from_ssdp_usn(usn: str) -> str | None:
    if not usn.startswith("uuid:"):
        return None
    return parse_device_uuid(usn.split("::", 1)[0].removeprefix("uuid:"))


def uuid_from_discovery(discovery_info: SsdpServiceInfo) -> str | None:
    """Device UUID from UPnP UDN or SSDP USN."""
    raw_udn = discovery_info.upnp.get(ATTR_UPNP_UDN)
    if raw_udn and (device_uuid := uuid_from_upnp_udn(raw_udn)):
        return device_uuid
    if discovery_info.ssdp_usn and (
        device_uuid := uuid_from_ssdp_usn(discovery_info.ssdp_usn)
    ):
        return device_uuid
    return None


def unique_id_for_discovery(discovery_info: SsdpServiceInfo, host: str) -> str:
    """Stable config-flow unique_id: device UUID if present, else host."""
    return uuid_from_discovery(discovery_info) or host


def host_from_ssdp(discovery_info: SsdpServiceInfo) -> str | None:
    """Host from SSDP location, headers, or USN."""
    if discovery_info.ssdp_location:
        try:
            if hostname := urlparse(discovery_info.ssdp_location).hostname:
                return str(hostname)
        except ValueError:
            pass
    if discovery_info.ssdp_headers:
        location_header = discovery_info.ssdp_headers.get("location")
        if isinstance(location_header, str):
            try:
                if hostname := urlparse(location_header).hostname:
                    return str(hostname)
            except ValueError:
                pass
    if discovery_info.ssdp_usn and "fritz.box" in discovery_info.ssdp_usn.lower():
        return "fritz.box"
    return None


def is_fritzbox_router_discovery(discovery_info: SsdpServiceInfo) -> bool:
    """Return True if SSDP data looks like a FRITZ!Box router (not a repeater)."""
    st = discovery_info.ssdp_st or ""
    usn = discovery_info.ssdp_usn or ""
    server = discovery_info.ssdp_server or ""
    location = discovery_info.ssdp_location or ""

    combined = f"{st} {usn} {server} {location}".lower()
    if discovery_info.ssdp_headers:
        headers_str = " ".join(
            str(value) for value in discovery_info.ssdp_headers.values()
        ).lower()
        combined += f" {headers_str}"

    if not any(indicator in combined for indicator in FRITZBOX_SSDP_INDICATORS):
        return False

    if any(indicator in combined for indicator in REPEATER_INDICATORS):
        return False

    has_igd = "internetgatewaydevice" in combined or "igd" in combined
    if not has_igd:
        return "fritz!box" in combined
    return True
