"""Tests for the Mikrotik component."""
from homeassistant.components import mikrotik

MOCK_DATA = {
    mikrotik.CONF_NAME: "Mikrotik",
    mikrotik.CONF_HOST: "0.0.0.0",
    mikrotik.CONF_USERNAME: "user",
    mikrotik.CONF_PASSWORD: "pass",
    mikrotik.CONF_PORT: 8278,
    mikrotik.CONF_VERIFY_SSL: False,
}

MOCK_OPTIONS = {
    mikrotik.CONF_ARP_PING: False,
    mikrotik.const.CONF_FORCE_DHCP: False,
    mikrotik.CONF_DETECTION_TIME: mikrotik.DEFAULT_DETECTION_TIME,
}

DEVICE_1_DHCP = {
    ".id": "*1A",
    "address": "0.0.0.1",
    "mac-address": "00:00:00:00:00:01",
    "active-address": "0.0.0.1",
    "host-name": "Device_1",
    "comment": "Mobile",
}
DEVICE_2_DHCP = {
    ".id": "*1B",
    "address": "0.0.0.2",
    "mac-address": "00:00:00:00:00:02",
    "active-address": "0.0.0.2",
    "host-name": "Device_2",
    "comment": "PC",
}
DEVICE_1_WIRELESS = {
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

DEVICE_2_WIRELESS = {
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
