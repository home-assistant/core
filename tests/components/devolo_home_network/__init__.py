"""Tests for the devolo Home Network integration."""

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
