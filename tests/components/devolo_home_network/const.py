"""Constants used for mocking data."""

from homeassistant.components import zeroconf

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

DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    host=IP,
    port=14791,
    hostname="test.local.",
    type="_dvl-deviceapi._tcp.local.",
    name="dLAN pro 1200+ WiFi ac._dvl-deviceapi._tcp.local.",
    properties={
        "Path": "abcdefghijkl/deviceapi",
        "Version": "v0",
        "Product": "dLAN pro 1200+ WiFi ac",
        "Features": "reset,update,led,intmtg,wifi1",
        "MT": "2730",
        "SN": "1234567890",
        "FirmwareVersion": "5.6.1",
        "FirmwareDate": "2020-10-23",
        "PS": "",
        "PlcMacAddress": "AA:BB:CC:DD:EE:FF",
    },
)

DISCOVERY_INFO_WRONG_DEVICE = zeroconf.ZeroconfServiceInfo(
    host="mock_host",
    hostname="mock_hostname",
    name="mock_name",
    port=None,
    properties={"MT": "2600"},
    type="mock_type",
)

NEIGHBOR_ACCESS_POINTS = {
    "neighbor_aps": [
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "ssid": "wifi",
            "band": "WIFI_BAND_2G",
            "channel": 1,
            "signal": -73,
            "signal_bars": 1,
        }
    ]
}

PLCNET = {
    "network": {
        "data_rates": [
            {
                "mac_address_from": "AA:BB:CC:DD:EE:FF",
                "mac_address_to": "11:22:33:44:55:66",
                "rx_rate": 0.0,
                "tx_rate": 0.0,
            },
        ],
        "devices": [],
    }
}
