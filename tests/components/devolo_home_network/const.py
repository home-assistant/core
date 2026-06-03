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

from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

IP = "192.0.2.1"
IP_ALT = "192.0.2.2"

CONNECTED_STATIONS = [
    ConnectedStationInfo(
        mac_address="00:00:5E:00:53:01",
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
        "PlcMacAddress": "00:00:5E:00:53:00",
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
        "PlcMacAddress": "00:00:5E:00:53:00",
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
        mac_address="00:00:5E:00:53:04",
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
            "mac_address": "00:00:5E:00:53:00",
            "attached_to_router": False,
            "topology": LOCAL,
            "user_device_name": "test1",
        },
        {
            "mac_address": "00:00:5E:00:53:02",
            "attached_to_router": True,
            "topology": REMOTE,
            "user_device_name": "test2",
        },
        {
            "mac_address": "00:00:5E:00:53:03",
            "attached_to_router": False,
            "topology": REMOTE,
            "user_device_name": "test3",
        },
    ],
    data_rates=[
        {
            "mac_address_from": "00:00:5E:00:53:00",
            "mac_address_to": "00:00:5E:00:53:02",
            "rx_rate": 100.0,
            "tx_rate": 100.0,
        },
        {
            "mac_address_from": "00:00:5E:00:53:00",
            "mac_address_to": "00:00:5E:00:53:03",
            "rx_rate": 150.0,
            "tx_rate": 150.0,
        },
    ],
)

PLCNET_ATTACHED = LogicalNetwork(
    devices=[
        {
            "mac_address": "00:00:5E:00:53:00",
            "attached_to_router": True,
        }
    ],
    data_rates=[
        {
            "mac_address_from": "00:00:5E:00:53:00",
            "mac_address_to": "00:00:5E:00:53:02",
            "rx_rate": 100.0,
            "tx_rate": 100.0,
        },
        {
            "mac_address_from": "00:00:5E:00:53:00",
            "mac_address_to": "00:00:5E:00:53:03",
            "rx_rate": 150.0,
            "tx_rate": 150.0,
        },
    ],
)

UPTIME = 100
