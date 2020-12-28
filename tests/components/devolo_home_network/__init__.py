"""Tests for the devolo Home Network integration."""

from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DISCOVERY_INFO = {
    "host": "1.1.1.1",
    "port": 14791,
    "hostname": "test.local.",
    "type": "_dvl-deviceapi._tcp.local.",
    "name": "dLAN pro 1200+ WiFi ac._dvl-deviceapi._tcp.local.",
    "properties": {
        "Path": "abcdefghijkl/deviceapi",
        "Version": "v0",
        "Product": "dLAN pro 1200+ WiFi ac",
        "Features": "reset,update,led,intmtg,wifi1",
        "MT": "2730",
        "SN": "1234567890",
        "FirmwareVersion": "5.6.1",
        "FirmwareDate": "2020-10-23",
        "PS": "",
    },
}

DISCOVERY_INFO_WRONG_DEVICE = {"properties": {"MT": "2600"}}


def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    config = {
        CONF_IP_ADDRESS: "1.1.1.1",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    return entry
