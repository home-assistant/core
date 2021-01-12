"""Tests for the devolo Home Network integration."""

from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

IP = "1.1.1.1"

CONNECTED_STATIONS = {
    "connected_stations": [
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "vap_type": "WIFI_VAP_MAIN_AP",
            "band": "WIFI_BAND_5G",
            "rx_rate": 87800,
            "tx_rate": 87800,
        }
    ],
}

DISCOVERY_INFO = {
    "host": IP,
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
        "PlcMacAddress": "AABBCCDDEEFF",
    },
}

DISCOVERY_INFO_WRONG_DEVICE = {"properties": {"MT": "2600"}}

PLCNET = {
    "network": {
        "data_rates": [
            {
                "mac_address_from": "AABBCCDDEEFF",
                "mac_address_to": "112233445566",
                "rx_rate": 0.0,
                "tx_rate": 0.0,
            },
        ],
        "devices": [],
    }
}


def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    config = {
        CONF_IP_ADDRESS: IP,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    return entry
