"""Common for upnp."""

from urllib.parse import urlparse

from homeassistant.components import ssdp

TEST_UDN = "uuid:device"
TEST_ST = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
TEST_USN = f"{TEST_UDN}::{TEST_ST}"
TEST_LOCATION = "http://192.168.1.1/desc.xml"
TEST_HOSTNAME = urlparse(TEST_LOCATION).hostname
TEST_FRIENDLY_NAME = "friendly name"
TEST_DISCOVERY = {
    ssdp.ATTR_SSDP_LOCATION: TEST_LOCATION,
    ssdp.ATTR_SSDP_ST: TEST_ST,
    ssdp.ATTR_SSDP_USN: TEST_USN,
    ssdp.ATTR_UPNP_UDN: TEST_UDN,
    "usn": TEST_USN,
    "location": TEST_LOCATION,
    "_host": TEST_HOSTNAME,
    "_udn": TEST_UDN,
    "friendlyName": TEST_FRIENDLY_NAME,
}
