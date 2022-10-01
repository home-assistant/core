"""Tests for Kaleidescape integration."""

from homeassistant.components import ssdp
from homeassistant.components.ssdp import ATTR_UPNP_FRIENDLY_NAME, ATTR_UPNP_SERIAL

MOCK_HOST = "127.0.0.1"
MOCK_SERIAL = "123456"
MOCK_NAME = "Theater"

MOCK_SSDP_DISCOVERY_INFO = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=f"http://{MOCK_HOST}",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: MOCK_NAME,
        ATTR_UPNP_SERIAL: MOCK_SERIAL,
    },
)
