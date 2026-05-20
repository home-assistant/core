"""Tests for SSDP helpers."""

from unittest.mock import patch

from homeassistant.components.fritzbox_vpn.ssdp_unique_id import (
    host_from_ssdp,
    is_fritzbox_router_discovery,
    parse_device_uuid,
    unique_id_for_discovery,
    uuid_from_discovery,
    uuid_from_ssdp_usn,
    uuid_from_upnp_udn,
)
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

MOCK_DEVICE_UUID = "2f402f80-da79-4e15-8e7b-4b6b6b6b6b6b"
MOCK_UDN = f"uuid:{MOCK_DEVICE_UUID}"
MOCK_USN = f"uuid:{MOCK_DEVICE_UUID}::upnp:rootdevice"
MOCK_HOST = "192.168.178.1"


def _fritz_discovery(**kwargs: object) -> SsdpServiceInfo:
    """SSDP discovery payload that passes router detection."""
    defaults: dict = {
        "ssdp_st": "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        "ssdp_usn": MOCK_USN,
        "ssdp_location": f"https://{MOCK_HOST}:49000/",
        "ssdp_server": "Linux/3.10 UPnP/1.0 AVM FRITZ!Box 7530",
        "upnp": {ATTR_UPNP_FRIENDLY_NAME: "FRITZ!Box 7530", ATTR_UPNP_UDN: MOCK_UDN},
    }
    defaults.update(kwargs)
    return SsdpServiceInfo(**defaults)


def test_parse_device_uuid_accepts_valid_uuid() -> None:
    """Test parse_device_uuid accepts a valid UUID string."""
    assert parse_device_uuid(MOCK_DEVICE_UUID) == MOCK_DEVICE_UUID


def test_parse_device_uuid_rejects_invalid() -> None:
    """Test parse_device_uuid rejects invalid values."""
    assert parse_device_uuid("not-a-uuid") is None
    assert parse_device_uuid("") is None


def test_uuid_from_upnp_udn() -> None:
    """Test uuid_from_upnp_udn parses UDN values."""
    assert uuid_from_upnp_udn(MOCK_UDN) == MOCK_DEVICE_UUID
    assert uuid_from_upnp_udn("uuid:not-a-uuid") is None


def test_uuid_from_ssdp_usn() -> None:
    """Test uuid_from_ssdp_usn parses USN values."""
    assert uuid_from_ssdp_usn(MOCK_USN) == MOCK_DEVICE_UUID


def test_uuid_from_ssdp_usn_ignores_non_uuid_prefix() -> None:
    """Test uuid_from_ssdp_usn ignores non-uuid USN prefixes."""
    assert uuid_from_ssdp_usn("mock_usn") is None


def test_uuid_from_discovery_prefers_udn() -> None:
    """Test uuid_from_discovery prefers UPnP UDN."""
    assert uuid_from_discovery(_fritz_discovery()) == MOCK_DEVICE_UUID


def test_uuid_from_discovery_falls_back_to_usn() -> None:
    """Test uuid_from_discovery falls back to SSDP USN."""
    discovery = _fritz_discovery(upnp={ATTR_UPNP_FRIENDLY_NAME: "FRITZ!Box 7530"})
    assert uuid_from_discovery(discovery) == MOCK_DEVICE_UUID


def test_uuid_from_discovery_invalid_udn_uses_usn() -> None:
    """Test uuid_from_discovery uses USN when UDN is invalid."""
    discovery = _fritz_discovery(
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name", ATTR_UPNP_UDN: "uuid:not-a-uuid"},
    )
    assert uuid_from_discovery(discovery) == MOCK_DEVICE_UUID


def test_unique_id_for_discovery_uses_host_without_uuid() -> None:
    """Test unique_id_for_discovery uses host when no UUID is found."""
    discovery = _fritz_discovery(
        ssdp_usn="mock_usn",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert unique_id_for_discovery(discovery, MOCK_HOST) == MOCK_HOST


def test_host_from_ssdp_location() -> None:
    """Test host_from_ssdp parses ssdp_location."""
    assert host_from_ssdp(_fritz_discovery()) == MOCK_HOST


def test_host_from_ssdp_location_header() -> None:
    """Test host_from_ssdp parses location from SSDP headers."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location=None,
        ssdp_headers={"location": f"https://{MOCK_HOST}:49000/"},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert host_from_ssdp(discovery) == MOCK_HOST


def test_host_from_ssdp_fritz_box_from_usn() -> None:
    """Test host_from_ssdp extracts fritz.box from USN."""
    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:device-1::upnp:rootdevice://fritz.box",
        ssdp_st="mock_st",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert host_from_ssdp(discovery) == "fritz.box"


def test_host_from_ssdp_skips_non_string_header_location() -> None:
    """Test host_from_ssdp skips non-string location headers."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_headers={"location": 12345},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert host_from_ssdp(discovery) is None


def test_host_from_ssdp_empty_location_hostname_uses_headers() -> None:
    """Test host_from_ssdp uses headers when location hostname is empty."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location="http:///no-hostname",
        ssdp_headers={"location": f"https://{MOCK_HOST}:49000/"},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert host_from_ssdp(discovery) == MOCK_HOST


def test_host_from_ssdp_returns_none_without_location() -> None:
    """Test host_from_ssdp returns None without a location."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert host_from_ssdp(discovery) is None


def test_host_from_ssdp_header_value_error() -> None:
    """Test host_from_ssdp handles urlparse ValueError."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_headers={"location": "https://invalid.example"},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    with patch(
        "homeassistant.components.fritzbox_vpn.ssdp_unique_id.urlparse",
        side_effect=ValueError(),
    ):
        assert host_from_ssdp(discovery) is None


def test_is_fritzbox_router_discovery_accepts_router() -> None:
    """Test is_fritzbox_router_discovery accepts IGD routers."""
    assert is_fritzbox_router_discovery(_fritz_discovery()) is True


def test_is_fritzbox_router_discovery_rejects_unknown_device() -> None:
    """Test is_fritzbox_router_discovery rejects unknown devices."""
    discovery = SsdpServiceInfo(
        ssdp_st="urn:schemas-upnp-org:device:basic:1",
        ssdp_usn="uuid:other::device",
        ssdp_location="http://192.168.1.1/",
        ssdp_server="generic upnp",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Other"},
    )
    assert is_fritzbox_router_discovery(discovery) is False


def test_is_fritzbox_router_discovery_rejects_repeater() -> None:
    """Test is_fritzbox_router_discovery rejects repeaters."""
    discovery = _fritz_discovery(
        ssdp_server="AVM UPnP/1.0 fritz!wlan repeater 310",
    )
    assert is_fritzbox_router_discovery(discovery) is False


def test_is_fritzbox_router_discovery_fritzbox_without_igd() -> None:
    """Test is_fritzbox_router_discovery accepts Fritz!Box without IGD ST."""
    discovery = _fritz_discovery(
        ssdp_st="urn:schemas-upnp-org:device:fritzbox:1",
        ssdp_server="AVM FRITZ!Box 7530",
    )
    assert is_fritzbox_router_discovery(discovery) is True


def test_is_fritzbox_router_discovery_rejects_non_igd_non_fritzbox_name() -> None:
    """Test is_fritzbox_router_discovery rejects non-router AVM devices."""
    discovery = SsdpServiceInfo(
        ssdp_st="urn:schemas-upnp-org:device:avm:1",
        ssdp_usn="uuid:x::device",
        ssdp_location=f"https://{MOCK_HOST}/",
        ssdp_server="AVM device",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "AVM device"},
    )
    assert is_fritzbox_router_discovery(discovery) is False


def test_host_from_ssdp_skips_invalid_ssdp_location() -> None:
    """Malformed ssdp_location is ignored."""
    discovery = SsdpServiceInfo(
        ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        ssdp_usn=MOCK_USN,
        ssdp_location="://not-valid",
        ssdp_server="AVM FRITZ!Box 7530",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "FRITZ!Box", ATTR_UPNP_UDN: MOCK_UDN},
    )
    assert host_from_ssdp(discovery) is None


def test_host_from_ssdp_skips_invalid_location_header() -> None:
    """Malformed location header is ignored without raising."""
    discovery = SsdpServiceInfo(
        ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        ssdp_usn=MOCK_USN,
        ssdp_location=None,
        ssdp_server="AVM FRITZ!Box 7530",
        ssdp_headers={"location": "://not-a-valid-url"},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "FRITZ!Box", ATTR_UPNP_UDN: MOCK_UDN},
    )
    assert host_from_ssdp(discovery) is None


def test_host_from_ssdp_uses_valid_location_header() -> None:
    """Host can be parsed from SSDP headers when location is absent."""
    discovery = SsdpServiceInfo(
        ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        ssdp_usn=MOCK_USN,
        ssdp_location=None,
        ssdp_server="AVM FRITZ!Box 7530",
        ssdp_headers={"location": f"https://{MOCK_HOST}:49000/"},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "FRITZ!Box", ATTR_UPNP_UDN: MOCK_UDN},
    )
    assert host_from_ssdp(discovery) == MOCK_HOST


def test_is_fritzbox_router_discovery_includes_headers() -> None:
    """Test is_fritzbox_router_discovery inspects SSDP headers."""
    discovery = SsdpServiceInfo(
        ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        ssdp_usn=MOCK_USN,
        ssdp_location=f"https://{MOCK_HOST}/",
        ssdp_server="generic",
        ssdp_headers={"server": "AVM FRITZ!Box"},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name", ATTR_UPNP_UDN: MOCK_UDN},
    )
    assert is_fritzbox_router_discovery(discovery) is True
