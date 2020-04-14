"""Tests for the Mikrotik component."""
from homeassistant.components import mikrotik

MOCK_HUB1 = {
    mikrotik.CONF_HOST: "0.0.0.1",
    mikrotik.CONF_USERNAME: "user",
    mikrotik.CONF_PASSWORD: "pass",
    mikrotik.CONF_PORT: 8278,
    mikrotik.CONF_VERIFY_SSL: False,
}

MOCK_HUB2 = {
    mikrotik.CONF_HOST: "0.0.0.2",
    mikrotik.CONF_USERNAME: "user",
    mikrotik.CONF_PASSWORD: "pass",
    mikrotik.CONF_PORT: 8278,
    mikrotik.CONF_VERIFY_SSL: False,
}

ENTRY_DATA = {
    mikrotik.CONF_NAME: "Mikrotik",
    mikrotik.CONF_HUBS: {
        MOCK_HUB1[mikrotik.CONF_HOST]: MOCK_HUB1,
        MOCK_HUB2[mikrotik.CONF_HOST]: MOCK_HUB2,
    },
}

OLD_ENTRY_CONFIG = {
    mikrotik.CONF_NAME: "Mikrotik",
    mikrotik.CONF_HOST: "0.0.0.1",
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


ENTRY_OPTIONS = {}

HUB1_IDENTITY = [{"name": "HUB1"}]
HUB2_IDENTITY = [{"name": "HUB2"}]
HUB1_INFO = [{"serial-number": "11111"}]
HUB2_INFO = [{"serial-number": "11112"}]

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
    "comment": "PC1",
}

DEVICE_3_DHCP = {
    ".id": "*1C",
    "address": "0.0.0.3",
    "mac-address": "00:00:00:00:00:03",
    "active-address": "0.0.0.3",
    "host-name": "Device_3",
    "comment": "PC2",
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
}

DEVICE_3_WIRELESS = {
    ".id": "*266",
    "interface": "wlan1",
    "mac-address": "00:00:00:00:00:03",
    "ap": False,
    "wds": False,
    "bridge": False,
    "rx-rate": "72.2Mbps-20MHz/1S/SGI",
    "tx-rate": "72.2Mbps-20MHz/1S/SGI",
}

HUB1_DHCP_DATA = [DEVICE_1_DHCP, DEVICE_3_DHCP]
HUB2_DHCP_DATA = [DEVICE_2_DHCP]

HUB1_WIRELESS_DATA = [DEVICE_1_WIRELESS]
HUB2_WIRELESS_DATA = [DEVICE_2_WIRELESS]

HUB1_ARP_DATA = [
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
        "address": "0.0.0.3",
        "mac-address": "00:00:00:00:00:03",
        "interface": "bridge",
        "published": False,
        "invalid": False,
        "DHCP": True,
        "dynamic": True,
        "complete": True,
        "disabled": False,
    },
]

HUB2_ARP_DATA = [
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
