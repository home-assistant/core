"""Constants used for mocking data."""

from ipaddress import ip_address

from devolo_plc_api.device_api import (
    UPDATE_AVAILABLE,
    WIFI_BAND_2G,
    WIFI_BAND_5G,
    WIFI_VAP_MAIN_AP,
    ConnectedStationInfo,
    NeighborAPInfo,
    UpdateFirmwareCheck,
    WifiGuestAccessGet,
)
from devolo_plc_api.plcnet_api import LOCAL, REMOTE, LogicalNetwork

from homeassistant.components.zeroconf import ZeroconfServiceInfo

IP = "192.0.2.1"
IP_ALT = "192.0.2.2"

CONNECTED_STATIONS = [
    ConnectedStationInfo(
        mac_address="AA:BB:CC:DD:EE:FF",
        vap_type=WIFI_VAP_MAIN_AP,
        band=WIFI_BAND_5G,
        rx_rate=87800,
        tx_rate=87800,
    )
]

NO_CONNECTED_STATIONS = []

DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=ip_address(IP),
    ip_addresses=[ip_address(IP)],
    port=14791,
    hostname="test.local.",
    type="_dvl-deviceapi._tcp.local.",
    name="dLAN pro 1200+ WiFi ac._dvl-deviceapi._tcp.local.",
    properties={
        "Path": "abcdefghijkl/deviceapi",
        "Version": "v0",
        "Product": "dLAN pro 1200+ WiFi ac",
        "Features": "intmtg1,led,reset,restart,update,wifi1",
        "MT": "2730",
        "SN": "1234567890",
        "FirmwareVersion": "5.6.1",
        "FirmwareDate": "2020-10-23",
        "PS": "",
        "PlcMacAddress": "AA:BB:CC:DD:EE:FF",
    },
)

DISCOVERY_INFO_CHANGED = ZeroconfServiceInfo(
    ip_address=ip_address(IP_ALT),
    ip_addresses=[ip_address(IP_ALT)],
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

DISCOVERY_INFO_WRONG_DEVICE = ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.2"),
    ip_addresses=[ip_address("127.0.0.2")],
    hostname="mock_hostname",
    name="mock_name",
    port=None,
    properties={"MT": "2600"},
    type="mock_type",
)

FIRMWARE_UPDATE_AVAILABLE = UpdateFirmwareCheck(
    result=UPDATE_AVAILABLE, new_firmware_version="5.6.2_2023-01-15"
)

GUEST_WIFI = WifiGuestAccessGet(
    ssid="devolo-guest-930",
    key="HMANPGBA",
    enabled=False,
    remaining_duration=0,
)

GUEST_WIFI_CHANGED = WifiGuestAccessGet(
    ssid="devolo-guest-930",
    key="HMANPGAS",
    enabled=False,
    remaining_duration=0,
)

NEIGHBOR_ACCESS_POINTS = [
    NeighborAPInfo(
        mac_address="AA:BB:CC:DD:EE:FF",
        ssid="wifi",
        band=WIFI_BAND_2G,
        channel=1,
        signal=-73,
        signal_bars=1,
    )
]

PLCNET = LogicalNetwork(
    devices=[
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "attached_to_router": False,
            "topology": LOCAL,
            "user_device_name": "test1",
        },
        {
            "mac_address": "11:22:33:44:55:66",
            "attached_to_router": True,
            "topology": REMOTE,
            "user_device_name": "test2",
        },
        {
            "mac_address": "12:34:56:78:9A:BC",
            "attached_to_router": False,
            "topology": REMOTE,
            "user_device_name": "test3",
        },
    ],
    data_rates=[
        {
            "mac_address_from": "AA:BB:CC:DD:EE:FF",
            "mac_address_to": "11:22:33:44:55:66",
            "rx_rate": 100.0,
            "tx_rate": 100.0,
        },
        {
            "mac_address_from": "AA:BB:CC:DD:EE:FF",
            "mac_address_to": "12:34:56:78:9A:BC",
            "rx_rate": 150.0,
            "tx_rate": 150.0,
        },
    ],
)

PLCNET_ATTACHED = LogicalNetwork(
    devices=[
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "attached_to_router": True,
        }
    ],
    data_rates=[
        {
            "mac_address_from": "AA:BB:CC:DD:EE:FF",
            "mac_address_to": "11:22:33:44:55:66",
            "rx_rate": 100.0,
            "tx_rate": 100.0,
        },
        {
            "mac_address_from": "AA:BB:CC:DD:EE:FF",
            "mac_address_to": "12:34:56:78:9A:BC",
            "rx_rate": 150.0,
            "tx_rate": 150.0,
        },
    ],
)
