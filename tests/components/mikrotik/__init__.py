"""Tests for the Mikrotik component."""
from unittest.mock import patch

from homeassistant.components import mikrotik
from homeassistant.components.mikrotik.const import (
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_FORCE_DHCP,
    DEFAULT_DETECTION_TIME,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry

MOCK_DATA = {
    CONF_NAME: "Mikrotik",
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_PORT: 8278,
    CONF_VERIFY_SSL: False,
}

MOCK_OPTIONS = {
    CONF_ARP_PING: False,
    CONF_FORCE_DHCP: False,
    CONF_DETECTION_TIME: DEFAULT_DETECTION_TIME,
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
DEVICE_3_DHCP_NUMERIC_NAME = {
    ".id": "*1C",
    "address": "0.0.0.3",
    "mac-address": "00:00:00:00:00:03",
    "active-address": "0.0.0.3",
    "host-name": 123,
    "comment": "Mobile",
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
    **DEVICE_1_WIRELESS,
    ".id": "*265",
    "mac-address": "00:00:00:00:00:02",
    "last-ip": "0.0.0.2",
}
DEVICE_3_WIRELESS = {
    **DEVICE_1_WIRELESS,
    ".id": "*266",
    "mac-address": "00:00:00:00:00:03",
    "last-ip": "0.0.0.3",
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


async def setup_mikrotik_entry(hass, **kwargs):
    """Set up Mikrotik integration successfully."""
    support_wireless = kwargs.get("support_wireless", True)
    dhcp_data = kwargs.get("dhcp_data", DHCP_DATA)
    wireless_data = kwargs.get("wireless_data", WIRELESS_DATA)

    def mock_command(self, cmd, params=None):
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIRELESS]:
            return support_wireless
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP]:
            return dhcp_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.WIRELESS]:
            return wireless_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.ARP]:
            return ARP_DATA
        return {}

    config_entry = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS
    )
    config_entry.add_to_hass(hass)

    if "force_dhcp" in kwargs:
        config_entry.options = {**config_entry.options, "force_dhcp": True}

    if "arp_ping" in kwargs:
        config_entry.options = {**config_entry.options, "arp_ping": True}

    with patch("librouteros.connect"), patch.object(
        mikrotik.hub.MikrotikData, "command", new=mock_command
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
