"""Tests for the Roku component."""
from homeassistant.components import ssdp, zeroconf
from homeassistant.components.ssdp import ATTR_UPNP_FRIENDLY_NAME, ATTR_UPNP_SERIAL

NAME = "Roku 3"
NAME_ROKUTV = '58" Onn Roku TV'

HOST = "192.168.1.160"
SSDP_LOCATION = "http://192.168.1.160/"
UPNP_FRIENDLY_NAME = "My Roku 3"
UPNP_SERIAL = "1GU48T017973"

MOCK_SSDP_DISCOVERY_INFO = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=SSDP_LOCATION,
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: UPNP_FRIENDLY_NAME,
        ATTR_UPNP_SERIAL: UPNP_SERIAL,
    },
)

HOMEKIT_HOST = "192.168.1.161"

MOCK_HOMEKIT_DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    host=HOMEKIT_HOST,
    addresses=[HOMEKIT_HOST],
    hostname="mock_hostname",
    name="onn._hap._tcp.local.",
    port=None,
    properties={
        zeroconf.ATTR_PROPERTIES_ID: "2d:97:da:ee:dc:99",
    },
    type="mock_type",
)
