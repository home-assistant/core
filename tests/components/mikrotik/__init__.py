"""Tests for the Mikrotik component."""
from typing import Final

from homeassistant.components.mikrotik.const import (
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_DHCP_SERVER_TRACK_MODE,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

MOCK_DATA_OLD: Final = {
    CONF_NAME: "Mikrotik",
    CONF_HOST: "0.0.0.1",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_PORT: 8278,
    CONF_VERIFY_SSL: False,
}

MOCK_DATA: Final = {
    CONF_HOST: "0.0.0.1",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_PORT: 8278,
    CONF_VERIFY_SSL: False,
}

MOCK_OPTIONS_OLD: Final = {
    CONF_ARP_PING: True,
    "force_dhcp": True,
    CONF_DETECTION_TIME: 300,
}
MOCK_OPTIONS: Final = {
    "force_dhcp": False,
    CONF_ARP_PING: False,
    CONF_DHCP_SERVER_TRACK_MODE: "DHCP lease",
    CONF_DETECTION_TIME: 200,
    CONF_SCAN_INTERVAL: 10,
}

DEVICE_1_DHCP: Final = {
    ".id": "*1A",
    "address": "0.0.0.1",
    "mac-address": "00:00:00:00:00:01",
    "active-address": "0.0.0.1",
    "host-name": "Device_1",
    "comment": "Mobile",
}
DEVICE_2_DHCP: Final = {
    ".id": "*1B",
    "address": "0.0.0.2",
    "mac-address": "00:00:00:00:00:02",
    "host-name": "Device_2",
    "comment": "PC",
}
DEVICE_1_WIRELESS: Final = {
    ".id": "*264",
    "interface": "wlan1",
    "mac-address": "00:00:00:00:00:01",
    "ap": False,
    "wds": False,
    "bridge": False,
    "rx-rate": "72.2Mbps-20MHz/1S/SGI",
    "tx-rate": "72.2Mbps-20MHz/1S/SGI",
    "packets": "59542,17464",
    "bytes": "17536671,2966351",
    "frames": "59542,17472",
    "frame-bytes": "17655785,2862445",
    "hw-frames": "78935,38395",
    "hw-frame-bytes": "25636019,4063445",
    "tx-frames-timed-out": 0,
    "uptime": "5h49m36s",
    "last-activity": "170ms",
    "signal-strength": "-62@1Mbps",
    "signal-to-noise": 52,
    "signal-strength-ch0": -63,
    "signal-strength-ch1": -69,
    "strength-at-rates": "-62@1Mbps 16s330ms,-64@6Mbps 13s560ms,-65@HT20-3 52m6s30ms,-66@HT20-4 52m4s350ms,-66@HT20-5 51m58s580ms,-65@HT20-6 51m24s780ms,-65@HT20-7 5s680ms",
    "tx-ccq": 93,
    "p-throughput": 54928,
    "last-ip": "0.0.0.1",
    "802.1x-port-enabled": True,
    "authentication-type": "wpa2-psk",
    "encryption": "aes-ccm",
    "group-encryption": "aes-ccm",
    "management-protection": False,
    "wmm-enabled": True,
    "tx-rate-set": "OFDM:6-54 BW:1x SGI:1x HT:0-7",
}

DEVICE_2_WIRELESS: Final = {
    ".id": "*265",
    "interface": "wlan1",
    "mac-address": "00:00:00:00:00:02",
    "ap": False,
    "wds": False,
    "bridge": False,
    "rx-rate": "72.2Mbps-20MHz/1S/SGI",
    "tx-rate": "72.2Mbps-20MHz/1S/SGI",
    "packets": "59542,17464",
    "bytes": "17536671,2966351",
    "frames": "59542,17472",
    "frame-bytes": "17655785,2862445",
    "hw-frames": "78935,38395",
    "hw-frame-bytes": "25636019,4063445",
    "tx-frames-timed-out": 0,
    "uptime": "5h49m36s",
    "last-activity": "170ms",
    "signal-strength": "-62@1Mbps",
    "signal-to-noise": 52,
    "signal-strength-ch0": -63,
    "signal-strength-ch1": -69,
    "strength-at-rates": "-62@1Mbps 16s330ms,-64@6Mbps 13s560ms,-65@HT20-3 52m6s30ms,-66@HT20-4 52m4s350ms,-66@HT20-5 51m58s580ms,-65@HT20-6 51m24s780ms,-65@HT20-7 5s680ms",
    "tx-ccq": 93,
    "p-throughput": 54928,
    "last-ip": "0.0.0.2",
    "802.1x-port-enabled": True,
    "authentication-type": "wpa2-psk",
    "encryption": "aes-ccm",
    "group-encryption": "aes-ccm",
    "management-protection": False,
    "wmm-enabled": True,
    "tx-rate-set": "OFDM:6-54 BW:1x SGI:1x HT:0-7",
}
DHCP_DATA = [DEVICE_1_DHCP, DEVICE_2_DHCP]

WIRELESS_DATA = [DEVICE_1_WIRELESS]

ARP_DATA = [
    {
        ".id": "*1",
        "address": "0.0.0.1",
        "mac-address": "00:00:00:00:00:01",
        "interface": "bridge",
        "published": False,
        "invalid": False,
        "DHCP": True,
        "dynamic": True,
        "complete": True,
        "disabled": False,
    },
    {
        ".id": "*2",
        "address": "0.0.0.2",
        "mac-address": "00:00:00:00:00:02",
        "interface": "bridge",
        "published": False,
        "invalid": False,
        "DHCP": True,
        "dynamic": True,
        "complete": True,
        "disabled": False,
    },
]

PING_SUCCESS = [
    {
        "seq": 0,
        "host": "192.168.3.18",
        "sent": 1,
        "received": 1,
    },
    {
        "seq": 1,
        "host": "F8:0D:60:35:12:B8",
        "time": "26ms",
        "sent": 2,
        "received": 2,
    },
    {
        "seq": 1,
        "host": "F8:0D:60:35:12:B8",
        "time": "26ms",
        "sent": 2,
        "received": 3,
    },
]

PING_FAIL = [
    {
        "seq": 0,
        "host": "192.168.3.18",
        "status": "timeout",
        "sent": 1,
        "received": 0,
        "packet-loss": 100,
    },
    {
        "seq": 1,
        "host": "F8:0D:60:35:12:B8",
        "status": "timeout",
        "sent": 2,
        "received": 0,
        "packet-loss": 100,
    },
    {
        "seq": 2,
        "host": "192.168.3.18",
        "status": "timeout",
        "sent": 3,
        "received": 0,
        "packet-loss": 100,
    },
]
